import sente
import glob
import re
import pandas as pd
import itertools
import json
import analysisengine
import os
from sgf2img import GetAllThemes, GameImageGenerator
from ast import literal_eval

position_label_dict = {
    'KL2L':[(3,2),(2,4),(2,7)],
    'HLA':[(3,3),(2,5),(3,5)],
    'SAV':[(3,2),(3,4),(2,4),(3,3),(2,3),(4,2)],
    'HLKA':[(3,3),(2,5),(5,2),(2,3),(2,2),(1,2)],
    'KH1L':[(3,2),(3,4),(2,6)],
    'KH2L':[(3,2),(3,4),(2,7)],
    'KL1H':[(3,2),(2,4),(3,6)],
    'KL1L':[(3,2),(2,4),(2,6)],
    'ENCLOSUREONEOFF':[(2,3)]
}
position_label_descriptions = {
    'KL2L':'Komoku, Low Approach, 2 Space Low Pincer',
    'HLA':'Hoshi, Low Approach, Attach On Top',
    'SAV':'Small Avalanche',
    'HLKA':'Hoshi, Low Approach, Knights move, Attach',
    'KH1L':'Komoku, High Approach, 1 Space Low Pincer',
    'KH2L':'Komoku, High Approach, 2 Space Low Pincer',
    'KL1H':'Komoku, Low Approach, 1 Space High Pincer',
    'KL1L':'Komoku, Low Approach, 1 Space Low Pincer',
    'ENCLOSUREONEOFF':'Komoku enclosures'
}

letter_map = {'A': 0,
 'B': 1,
 'C': 2,
 'D': 3,
 'E': 4,
 'F': 5,
 'G': 6,
 'H': 7,
 'J': 8,
 'K': 9,
 'L': 10,
 'M': 11,
 'N': 12,
 'O': 13,
 'P': 14,
 'Q': 15,
 'R': 16,
 'S': 17,
 'T': 18,
 '0': 'A',
 '1': 'B',
 '2': 'C',
 '3': 'D',
 '4': 'E',
 '5': 'F',
 '6': 'G',
 '7': 'H',
 '8': 'J',
 '9': 'K',
 '10': 'L',
 '11': 'M',
 '12': 'N',
 '13': 'O',
 '14': 'P',
 '15': 'Q',
 '16': 'R',
 '17': 'S',
 '18': 'T'}

def ref_seq(seq: list) -> list:
    return [sente.Move(m.get_y(),m.get_x(),m.get_stone()) for m in seq]

def rot_seq(seq: list) -> list:
    return [sente.Move(18 - m.get_y(),m.get_x(),m.get_stone()) for m in seq]

def seq_to_vert(seq: list) -> list:
    return [f'({m.get_x()},{m.get_y()})' for m in seq]

def get_scenarios(position_label: str) -> pd.DataFrame:
    matches_path = position_label + '\\matches.txt'
    matches_df = pd.read_csv(matches_path)
    matches_df['scenario_label'] = [f'{i:03}' for i in range(len(matches_df))]
    mod_seqs = []
    transformed_sequences = []
    for i in range(len(matches_df)):
        game = sente.sgf.load('..\\go4go_collection\\'+matches_df.fname[i])
        seq = game.get_default_sequence()[:matches_df.startindex[i]]
        mod_seq = seq.copy()
        for j in range(matches_df.reflection[i]):
            mod_seq = ref_seq(mod_seq)
        for j in range(matches_df.rotation[i]):
            mod_seq = rot_seq(mod_seq)
        mod_seqs.append(mod_seq)
        transformed_sequences.append(seq_to_vert(mod_seq))
    matches_df['mod_seq'] = mod_seqs
    matches_df['transformed_sequence'] = transformed_sequences
    return matches_df

def get_nodes(position_label: str) -> pd.DataFrame:
    tree = sente.sgf.load(position_label + '\\tree.sgf')
    tree_coords = [seq_to_vert(s) for s in tree.get_all_sequences()]
    dup_nodes = [l[:i] for l in tree_coords for i in range(len(l)+1)]
    dup_nodes.sort()
    tree_nodes = list(x for x, _ in itertools.groupby(dup_nodes))
    nodenames = [re.sub(r'[(),]','',"".join(x)) for x in tree_nodes]
    nodes_df = pd.DataFrame({'node_name':nodenames,
        'coord_list':tree_nodes})
    return nodes_df

def get_merge(position_label: str) -> pd.DataFrame:
    matches_df = get_scenarios(position_label)
    nodes_df = get_nodes(position_label)
    matches_df['dummy']="a"
    nodes_df['dummy']="a"
    merge_df = pd.merge(nodes_df,matches_df,on = 'dummy')
    merge_df['id'] = position_label + "_" + merge_df['node_name'] + "_" + merge_df['scenario_label']
    merge_df['verts'] = merge_df['transformed_sequence'] + merge_df['coord_list']
    merge_df['moves'] = [[[p,vert] for vert,p in zip(l,("BW"*200)[:len(l)])] for l in merge_df['verts']]
    return merge_df


def get_query(position_label: str) -> list:
    merge_df = get_merge(position_label)
    dictlist = [{
        'id': merge_df.id[i],
        'moves': merge_df.moves[i],
        "rules": "tromp-taylor",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19
    } for i in range(len(merge_df))]
    return dictlist

def run_query(position_label: str, max_queries: int = 1000) -> list:
    out_path = position_label + '\\raw_output.txt'
    existing_stringlist = []
    if glob.glob(out_path):
        with open(out_path,'r') as in_f:
            existing_stringlist = in_f.read().split(";")
    existing_ids = [json.loads(x)['id'] for x in existing_stringlist]
    full_query = get_query(position_label)
    q = [x for x in full_query if x['id'] not in existing_ids][:max_queries]
    print(len(q))
    if len(q) > 0:
        g = analysisengine.gtp(analysisengine.cmd)
        new_out_list = g.run_lists(q)
        g.close()
        g.terminate()
    else:
        new_out_list = []
    out_s = ";".join(existing_stringlist + new_out_list)
    with open(out_path,'w') as out_f:
        out_f.write(out_s)
    return out_s

def node_id_to_verts(node_id: str) -> list:
    node_id_parts = node_id.split("_")
    start_verts = position_label_dict[node_id_parts[0]]
    s = [int(x) for x in node_id_parts[1]]
    return start_verts + list(zip(s[::2],s[1::2]))

def vertlist_to_qimage(vertlist: list, size: int = 1024):
    g = sente.Game(19)
    for vert in vertlist:
        g.play(vert[0]+1,vert[1]+1)
    sente.sgf.dump(g,'temp.sgf')
    gig = GameImageGenerator(GetAllThemes()['print'],True)
    img = gig.get_game_image('temp.sgf',
    size,
    1,
    len(vertlist),
    len(vertlist),
    [1,9,10,19])
    os.remove('temp.sgf')
    return img

def vertlist_to_image(vertlist: list, seq_length: int = 1):
    g = sente.Game(19)
    for vert in vertlist:
        g.play(vert[0]+1,vert[1]+1)
    sente.sgf.dump(g,'temp.sgf')
    gig = GameImageGenerator(GetAllThemes()['subdued'],False)
    img = gig.get_game_image('temp.sgf',
    400,
    1,
    len(vertlist) + 1 - seq_length,
    len(vertlist),
    [1,1,19,19])
    os.remove('temp.sgf')
    return img

def get_results_df(position_label: str) -> pd.DataFrame:
    out_s = run_query(position_label,0)
    out_dicts = [json.loads(x) for x in out_s.split(";")]
    results_df = pd.DataFrame([{
        'id': d['id'],
        'top_move': d['moveInfos'][0]['move'],
        'top_seq': d['moveInfos'][0]['pv'],
        'scoreLead': -d['moveInfos'][0]['scoreLead'],
        'winrate': 1 - d['moveInfos'][0]['winrate']
    } for d in out_dicts])
    results_df['prev_id'] = [x[:-6] + x[-4:] if (len(x)>9) else None for x in results_df.id]
    return results_df

def get_delta_df(position_label: str) -> pd.DataFrame:
    results_df = get_results_df(position_label)
    prev_df = pd.DataFrame({
        'prev_id': results_df.id,
        'prev_move': results_df.top_move,
        'prev_scoreLead': results_df.scoreLead,
        'prev_winrate': results_df.winrate
    })
    delta_df = pd.merge(results_df,prev_df,on = 'prev_id')
    delta_df['delta_p'] = delta_df.scoreLead + delta_df.prev_scoreLead
    delta_df['delta_wr'] = delta_df.winrate + delta_df.prev_winrate - 1
    delta_df['node_name'] = delta_df.id.str.slice(0,-4)
    return delta_df.drop(columns=['prev_id', 'prev_scoreLead', 'prev_winrate'])

def save_qimages(position_label: str):
    merge_df = get_merge(position_label)
    merge_df['node_name'] = merge_df.id.str.slice(0,-4)
    for node_id in set(merge_df.node_name):
        outp = position_label + '\\qimages\\' + node_id +'.png'
        vertlist_to_qimage(node_id_to_verts(node_id)).save(outp)

def save_qimages_s(position_label: str):
    merge_df = get_merge(position_label)
    merge_df['node_name'] = merge_df.id.str.slice(0,-4)
    for node_id in set(merge_df.node_name):
        outp = position_label + '\\qimages\\' + node_id +'_s.png'
        vertlist_to_qimage(node_id_to_verts(node_id), 250).save(outp)

def save_images(position_label: str):
    """maybe change this so that it uses the raw output instead of merge. Would give diagrams for index"""
    merge_df = pd.merge(get_merge(position_label),get_results_df(position_label).loc[:,['id','top_seq']],on = 'id')
    for i in range(len(merge_df)):
        outp = position_label + '\\images\\' + merge_df.id[i] +'.png'
        vertlist = [literal_eval(x) for x in merge_df.verts[i]]
        vertlist += [(letter_map[x[0]],19-int(x[1:])) for x in merge_df.top_seq[i]]
        vertlist_to_image(vertlist,len(merge_df.top_seq[i])).save(outp)


def save_histograms(position_label: str):
    delta_df = get_delta_df(position_label)
    for node_id in set(delta_df.node_name):
        outp = position_label + '\\histograms\\' + node_id +'hist.png'
        ax = delta_df[delta_df.node_name == node_id].delta_p.plot.hist()
        fig = ax.get_figure()
        fig.savefig(outp)
        fig.clf()

def get_scenario_table_html(position_label: str) -> str:
    delta_df = get_delta_df(position_label)
    delta_df['img_html'] = '<img src="..\\images\\' + delta_df.id +'.png" alt="fig">\n'
    return delta_df.loc[:,['img_html','delta_p','delta_wr']].sort_values('delta_p').to_html()


def save_summaries(position_label: str):
    delta_df = get_delta_df(position_label)
    delta_df['img_html'] = 'zzzimg src="..\\images\\' + delta_df.id +'.png" alt="fig"yyy'#height=300 width=300yyy'
    for node_id in set(delta_df.node_name):
        filt_df = delta_df[delta_df.node_name == node_id]
        summary_table = filt_df.describe().loc[:,['delta_p','delta_wr']]
        outp = position_label + '\\summaries\\' + node_id +'.html'
        summary_table_html = summary_table.to_html()
        full_table_html = filt_df.loc[:,['img_html','top_seq','delta_p','delta_wr']].sort_values('delta_p').to_html()
        page = (
            '<!DOCTYPE html>\n<html>\n'
            '<head><link rel="stylesheet" href="..\\..\\basic.css"></head>'
            '<body>\n\n'
            f'<h1>{position_label_descriptions[position_label]}</h1>'
            f'<p>{get_breadcrumb(node_id)}</p>\n'
            '<div id="navigation">'
            '<h2>Previous moves</h2>'
            f'<p>{get_breadcrumb(node_id)}</p>\n'
            '<h2>Alternatives</h2>'
            #f'<p>Alternatives to {nodeid_to_lastboard(node_id)} in this corner pattern include.. </p>'
            f'<p>{"<br>".join(get_alternatives(node_id))}</p>'
            #'<h2>Katago follow ups</h2>'
            #f'<p>Katago considers the following moves after {nodeid_to_lastboard(node_id)} in this corner pattern.. </p>'
            '<h2>Human follow ups</h2>'
            #f'<p>Humans consider the following moves after {nodeid_to_lastboard(node_id)} in this corner pattern.. </p>'
            f'<p>{"<br>".join(get_followups(node_id))}</p>'
            '</div>'
            f'<img src="..\\qimages\\{node_id}.png" alt="fig">\n'
            '<div id="summary">'
            f'<img src="..\\histograms\\{node_id}hist.png" alt="hist">\n'
            f'\n{summary_table_html}\n'
            '</div>'
            f'\n{full_table_html}\n'
            '\n</body>\n</html>'
        )
        page = page.replace('zzz','<')
        page = page.replace('yyy','>')
        with open(outp,'w') as f:
            f.write(page)

def save_position_summary(position_label: str):
    #delta_df = get_delta_df(position_label)
    #delta_df['img_html'] = 'zzzimg src="..\\images\\' + delta_df.id +'.png" alt="fig"yyy'#height=300 width=300yyy'
    #filt_df = delta_df[delta_df.node_name == node_id]
    #summary_table = filt_df.describe().loc[:,['delta_p','delta_wr']]
    outp = position_label + '\\index.html'
    #summary_table_html = summary_table.to_html()
    #full_table_html = filt_df.loc[:,['img_html','top_seq','delta_p','delta_wr']].sort_values('delta_p').to_html()
    page = (
        '<!DOCTYPE html>\n<html>\n'
        '<head><link rel="stylesheet" href="..\\basic.css"></head>'
        '<body>\n\n'
        f'<h1>{position_label_descriptions[position_label]}</h1>'
        '<div id="navigation">'
        '<h2>Human follow ups</h2>'
        f'<p>{"<br>".join(get_followups(position_label+"_"))}</p>'
        '</div>'
        f'<img src="..\\qimages\\{position_label+"_"}.png" alt="fig">\n'
        #f'\n{full_table_html}\n'
        '\n</body>\n</html>'
    )
    page = page.replace('zzz','<')
    page = page.replace('yyy','>')
    with open(outp,'w') as f:
        f.write(page)

def nodeid_to_lastboard(nodeid: str) -> str:
    underscore_loc = nodeid.find('_')+1
    if len(nodeid)>underscore_loc:
        lb = letter_map[nodeid[-2:-1]] + str(19 - int(nodeid[-1:]))
    else:
        lb = "Root"
    return lb

def node_to_link(nodeid: str) -> str:
    return f'<a href="{nodeid}.html">{nodeid_to_lastboard(nodeid)}</a>'

def get_breadcrumb(nodeid: str) -> str:
    underscore_loc = nodeid.find('_')+1
    prevnodes = [nodeid[:underscore_loc+2*n] for n in range(int((len(nodeid)-5)/2))]
    prevlinks = [node_to_link(nodeid) for nodeid in prevnodes]
    return " _ ".join(prevlinks)

def get_alternatives(nodeid: str) -> str:
    underscore_loc = nodeid.find('_')
    pattern_name = nodeid[:underscore_loc]
    altnos = [x for x in get_nodes(pattern_name).node_name if x[:-2] == nodeid[underscore_loc+1:-2]]
    return [node_to_link(pattern_name + '_' + no) for no in altnos]

def get_followups(nodeid: str) -> str:
    underscore_loc = nodeid.find('_')
    pattern_name = nodeid[:underscore_loc]
    folnos = [x for x in get_nodes(pattern_name).node_name if x[:-2] == nodeid[underscore_loc+1:]]
    return [node_to_link(pattern_name + '_' + no) for no in folnos]

def run_position(position_label: str, max_queries: int = 1000):
    run_query(position_label,max_queries)
    save_qimages(position_label)
    save_qimages_s(position_label)
    save_images(position_label)
    save_histograms(position_label)
    save_summaries(position_label)