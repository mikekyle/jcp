# -*- coding: utf-8 -*-


import subprocess,sys
import threading, queue
import json
from time import sleep
#from toolbox import log

loglock=threading.Lock()
def log(*args):
	global loglock
	loglock.acquire()
	encoding=sys.stdout.encoding
	for arg in args:
		try:
			if type(arg)==type(str('abc')):
				arg=arg#.decode('utf-8',errors='replace')
			elif type(arg)!=type('abc'):
				try:
					arg=str(arg)
				except:
					arg=str(arg,errors='replace')
				arg=arg#.decode('utf-8',errors='replace')
			arg=arg.encode(encoding, errors='replace')
			print(arg, end=' ')
		except:
			print("?"*len(arg), end=' ')
	print()
	loglock.release()

cmd = [
    "C:/baduk/lizzie/katago.exe",
    "analysis",
    "-config C:/baduk/lizzie/analysis_example.cfg",
    "-model C:/baduk/lizzie/kg40train.bin.gz",
]

class gtp():
        def __init__(self,command):
                self.c=1
                self.command_line=command[0]+" "+" ".join(command[1:])
                #command=[c.encode(sys.getfilesystemencoding()) for c in command]
                #command=" ".join([c.encode(sys.getfilesystemencoding()) for c in command])
                command=" ".join(command)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                self.process=subprocess.Popen(command, startupinfo=startupinfo, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.size=0
                self.stderr_queue=queue.Queue()
                self.stdout_queue=queue.Queue()
                threading.Thread(target=self.consume_stderr).start()
                self.free_handicap_stones=[]
                self.history=[]

        ####low level function####
        def consume_stderr(self):
                while 1:
                        try:
                                err_line=self.process.stderr.readline().decode("utf-8")
                                if err_line:
                                        self.stderr_queue.put(err_line)
                                else:
                                        #log("leaving consume_stderr thread")
                                        return
                        except Exception as e:
                                log("leaving consume_stderr thread due to exception")
                                log(e)
                                return
        
        def consume_stdout(self):
                while 1:
                        try:
                                line=self.process.stdout.readline().decode("utf-8")
                                if line:
                                        self.stdout_queue.put(line)
                                else:
                                        log("leaving consume_stdout thread")
                                        return
                        except Exception as e:
                                log("leaving consume_stdout thread due to exception")
                                log(e)
                                return
                
        def write(self,txt):
                try:
                        self.process.stdin.write(txt+b"\n")
                        self.process.stdin.flush()
                except Exception as e:
                        log("Error while writting to stdin\n"+str(e))
                #self.process.stdin.write(str(self.c)+" "+txt+"\n")
                self.c+=1
        
        def readline(self):
                answer=self.process.stdout.readline().decode("utf-8")
                while answer in ("\n","\r\n","\r"):
                        answer=self.process.stdout.readline().decode("utf-8")
                return answer
        
        ####hight level function####
        def run_lists(self,list_of_dicts):
                """Takes list of dicts, writes them all to the engine, returns a list of json outputs/dicts"""
                outlist = []
                for movedict in list_of_dicts:
                        movebin = (json.dumps(movedict)+'\n').encode(sys.getfilesystemencoding())
                        self.write(movebin)
                for i in range(len(list_of_dicts)):
                        l = self.readline()
                        if len(l) > 20:
                                #print('parsing:===========',l)
                                #d = json.loads(l)
                                #d.update(d['moveInfos'][0])
                                #d.update(d['rootInfo'])
                                #outlist.append(d)
                                outlist.append(l)
                        else:
                                print('Readline produced "',l,'"\n')
                return outlist

        def diagnostic(self,list_of_dicts):
                """Runs list of dicts one at a time to find bugs"""
                i = 1
                for movedict in list_of_dicts:
                        print(i,'\n',movedict, '\n')
                        movebin = (json.dumps(movedict)+'\n').encode(sys.getfilesystemencoding())
                        self.write(movebin)
                        l = self.readline()
                        print('Readline "',l[:30],'..."')
                        i+=1
        
        def quit(self):
                self.write(b"-quit-without-waiting")
                answer=self.readline()
                if answer[0]=="=":return True
                else:return False       

        def terminate(self):
                t=10
                while 1:
                        self.quitting_thread.join(0.0)  
                        if not self.quitting_thread.is_alive():
                                log("The bot has quitted properly")
                                break
                        elif t==0:
                                log("The bot is still running...")
                                log("Forcefully closing it now!")
                                break
                        t-=1
                        log("Waiting for the bot to close",t,"s")
                        sleep(1)
                
                try: self.process.kill()
                except: pass
                try: self.process.stdin.close()
                except: pass
                
        def close(self):
                log("Now closing")
                self.quitting_thread=threading.Thread(target=self.quit)
                self.quitting_thread.start()
                threading.Thread(target=self.terminate).start()
