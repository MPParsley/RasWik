#!/usr/bin/env python
import Tkinter as tk
import ttk
import sys
import os
import subprocess
import argparse
import json
import urllib2
import httplib
import shutil
import ConfigParser
import tkMessageBox
import threading
import Queue

class SandyLauncher:
    def __init__(self):
        self.debug = False # until we read config
        self.debugArg = False # or get command line
        self.configFileDefault = "Python/sandy_default.cfg"
        self.configFile = "Python/sandy.cfg"
        self.appFile = "Python/AppList.json"

        self.widthMain = 550
        self.heightMain = 300
        self.heightTab = self.heightMain - 40
        self.proc = []
        self.disableLaunch = False
        self.updateAvailable = False

        
        self._running = False
    
    def on_excute(self):
        self.readConfig()
        self.checkArgs()
        self.loadApps()

        self._running = True


        self.runLauncher()

        self.cleanUp()

    def endLauncher(self):
        self.debugPrint("End Launcher")
        position = self.master.geometry().split("+")
        self.config.set('Launcher', 'window_width_offset', position[1])
        self.config.set('Launcher', 'window_height_offset', position[2])
        self.master.destroy()
        self._running = False

    def cleanUp(self):
        self.debugPrint("Clean up and exit")
        # disconnect resources
        # kill child's??
        for c in self.proc:
            if c.poll() == None:
                c.terminate()
        self.writeConfig()
    
    def debugPrint(self, msg):
        if self.debug or self.debugArg:
            print(msg)

    def checkArgs(self):
        self.debugPrint("Parse Args")
        parser = argparse.ArgumentParser(description='Sandy Launcher')
        parser.add_argument('-u', '--noupdate',
                            help='disable checking for update',
                            action='store_false')
        parser.add_argument('-d', '--debug',
                            help='Extra Debug Output, overrides sandy.cfg setting',
                            action='store_true')
        
        args = parser.parse_args()
        
        if args.debug:
            self.debugArg = True

        if args.noupdate:
            self.checkForUpdate()

    def checkForUpdate(self):
        self.debugPrint("Checking for update")
        # go download version file
        try:
            request = urllib2.urlopen(self.config.get('Update', 'updateurl') +
                                      self.config.get('Update', 'versionfile'))
            self.newVersion = request.read()

        except urllib2.HTTPError, e:
            self.debugPrint('Unable to get latest version info - HTTPError = ' +
                            str(e.reason))
            self.newVersion = False

        except urllib2.URLError, e:
            self.debugPrint('Unable to get latest version info - URLError = ' +
                            str(e.reason))
            self.newVersion = False
        
        except httplib.HTTPException, e:
            self.debugPrint('Unable to get latest version info - HTTPException')
            self.newVersion = False

        except Exception, e:
            import traceback
            self.debugPrint('Unable to get latest version info - Exception = ' +
                            traceback.format_exc())
            self.newVersion = False

        if self.newVersion:
            self.debugPrint(
                "Latest Version: {}, Current Version: {}".format(
                              self.newVersion,self.currentVersion)
                            )
            if float(self.currentVersion) < float(self.newVersion):
                self.debugPrint("New Version Available")
                self.updateAvailable = True
        else:
            self.debugPrint("Could not check for new Version")
            
        
    def offerUpdate(self):
        self.debugPrint("Ask to update")
        if tkMessageBox.askyesno("WIK Update Available", "There is an update for WIK available would you like to download it?"):
            self.updateFailed = False
            # grab zip size for progress bar length
            try:
                u = urllib2.urlopen(self.config.get('Update', 'updateurl') + self.config.get('Update', 'updatefile').format(self.newVersion))
                meta = u.info()
                self.file_size = int(meta.getheaders("Content-Length")[0])
            except urllib2.HTTPError, e:
                self.debugPrint('Unable to get download file size - HTTPError = ' +
                                str(e.reason))
                self.updateFailed = "Unable to get download file size"
            
            except urllib2.URLError, e:
                self.debugPrint('Unable to get download file size- URLError = ' +
                                str(e.reason))
                self.updateFailed = "Unable to get download file size"
            
            except httplib.HTTPException, e:
                self.debugPrint('Unable to get download file size- HTTPException')
                self.updateFailed = "Unable to get download file size"
            
            except Exception, e:
                import traceback
                self.debugPrint('Unable to get download file size - Exception = ' +
                                traceback.format_exc())
                self.updateFailed = "Unable to get download file size"
            
            if self.updateFailed:
                tkMessageBox.showerror("Update Failed", self.updateFailed)
            else:
                position = self.master.geometry().split("+")
                
                self.progressWindow = tk.Toplevel()
                self.progressWindow.geometry("+{}+{}".format(
                                                int(position[1])+self.widthMain/4,
                                                int(position[2])+self.heightMain/4
                                                             )
                                             )
                self.progressWindow.title("Downloading Zip Files")
                
                tk.Label(self.progressWindow, text="Downloading Zip Progress").pack()
                
                self.progressBar = tk.IntVar()
                ttk.Progressbar(self.progressWindow, orient="horizontal",
                                length=200, mode="determinate",
                                maximum=self.file_size,
                                variable=self.progressBar).pack()
                
                self.downloadThread = threading.Thread(target=self.downloadUpdate)
                self.progressQueue = Queue.Queue()
                self.downloadThread.start()
                self.progressUpdate()

    def progressUpdate(self):
        self.debugPrint("Progress Update")
        value = self.progressQueue.get()
        self.progressBar.set(value)
        self.progressQueue.task_done()
        if self.updateFailed:
            self.progressWindow.destroy()
            tkMessageBox.showerror("Update Failed", self.updateFailed)
        elif value < self.file_size:
            self.master.after(5, self.progressUpdate)
        else:
            self.progressWindow.destroy()
            self.doUpdate(self.config.get('Update', 'downloaddir') + self.config.get('Update', 'updatefile').format(self.newVersion))

    def downloadUpdate(self):
        self.debugPrint("Downloading Update Zip")
        
        url = self.config.get('Update', 'updateurl') + self.config.get('Update', 'updatefile').format(self.newVersion)
        self.debugPrint(url)
        # mk dir Download
        if not os.path.exists(self.config.get('Update', 'downloaddir')):
            os.makedirs(self.config.get('Update', 'downloaddir'))
        
        localFile = self.config.get('Update', 'downloaddir') + self.config.get('Update', 'updatefile').format(self.newVersion)
        
        self.debugPrint(localFile)

        try:
            u = urllib2.urlopen(url)
            f = open(localFile, 'wb')
            meta = u.info()
            file_size = int(meta.getheaders("Content-Length")[0])
            self.debugPrint("Downloading: {0} Bytes: {1}".format(url, file_size))

            file_size_dl = 0
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
                
                file_size_dl += len(buffer)
                f.write(buffer)
                p = float(file_size_dl) / file_size
                status = r"{0}  [{1:.2%}]".format(file_size_dl, p)
                status = status + chr(8)*(len(status)+1)
                self.debugPrint(status)
                self.progressQueue.put(file_size_dl)

            f.close()
        except urllib2.HTTPError, e:
            self.debugPrint('Unable to get download file - HTTPError = ' +
                            str(e.reason))
            self.updateFailed = "Unable to get download file"
        
        except urllib2.URLError, e:
            self.debugPrint('Unable to get download file - URLError = ' +
                            str(e.reason))
            self.updateFailed = "Unable to get download file"
        
        except httplib.HTTPException, e:
            self.debugPrint('Unable to get download file - HTTPException')
            self.updateFailed = "Unable to get download file"
        
        except Exception, e:
            import traceback
            self.debugPrint('Unable to get download file - Exception = ' +
                            traceback.format_exc())
            self.updateFailed = "Unable to get download file"

    def manualZipUpdate(self):
        self.debugPrint("Location Zip for Update")
            
    def doUpdate(self, file):
        self.debugPrint("Doing Update with file: {}".format(file))
        

    def runLauncher(self):
        self.debugPrint("Running Main Launcher")
        self.master = tk.Tk()
        self.master.protocol("WM_DELETE_WINDOW", self.endLauncher)
        self.master.geometry(
             "{}x{}+{}+{}".format(self.widthMain,
                                  self.heightMain,
                                  self.config.get('Launcher',
                                                  'window_width_offset'),
                                  self.config.get('Launcher',
                                                  'window_height_offset')
                                  )
                             )
                             
        self.master.title("WIK Launcher v{}".format(self.currentVersion))
        #self.master.resizable(0,0)
        
        
        self.tabFrame = tk.Frame(self.master, name='tabFrame')
        self.tabFrame.pack(pady=2)
        
        self.initTabBar()
        self.initMain()
        self.initAdvanced()
        
        self.tBarFrame.show()
        
        if self.updateAvailable:
            self.master.after(500, self.offerUpdate)
        
        self.master.mainloop()

    def initTabBar(self):
        self.debugPrint("Setting up TabBar")
        # tab button frame
        self.tBarFrame = TabBar(self.tabFrame, "Main", fname='tabBar')
        self.tBarFrame.config(relief=tk.RAISED, pady=4)
        
        # tab buttons
        tk.Button(self.tBarFrame, text='Quit', command=self.endLauncher
               ).pack(side=tk.RIGHT)
        #tk.Label(self.tBarFrame, text=self.currentVersion).pack(side=tk.RIGHT)

    def initMain(self):
        self.debugPrint("Setting up Main Tab")
        iframe = Tab(self.tabFrame, "Main", fname='launcher')
        iframe.config(relief=tk.RAISED, borderwidth=2, width=self.widthMain,
                      height=self.heightTab)
        self.tBarFrame.add(iframe)
        
        
        #canvas = tk.Canvas(iframe, bd=0, width=self.widthMain-4,
        #                       height=self.heightTab-4, highlightthickness=0)
        #canvas.grid(row=0, column=0, columnspan=3, rowspan=5)

        tk.Canvas(iframe, bd=0, highlightthickness=0, width=self.widthMain-4,
                  height=28).grid(row=1, column=1, columnspan=3)
        tk.Canvas(iframe, bd=0, highlightthickness=0, width=150,
                  height=self.heightTab-4).grid(row=1, column=1, rowspan=3)
        
        tk.Label(iframe, text="Select an App to Launch").grid(row=1, column=1,
                                                              sticky=tk.W)
        
        lbframe = tk.Frame(iframe, bd=2, relief=tk.SUNKEN)

        self.scrollbar = tk.Scrollbar(lbframe)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.appSelect = tk.Listbox(lbframe, bd=0, height=10,
                                    yscrollcommand=self.scrollbar.set)
        self.appSelect.bind('<<ListboxSelect>>', self.onAppSelect)
        self.appSelect.pack()

        self.scrollbar.config(command=self.appSelect.yview)

        lbframe.grid(row=2, column=1, sticky=tk.W+tk.E+tk.N+tk.S, padx=2)

        for n in range(len(self.appList)):
            self.appSelect.insert(n, "{}: {}".format(n+1,
                                                     self.appList[n]['Name']))

        self.launchButton = tk.Button(iframe, text="Launch",
                                      command=self.launch,)
        self.launchButton.grid(row=3, column=1)

        if self.disableLaunch:
            self.launchButton.config(state=tk.DISABLED)

        self.appText = tk.Label(iframe, text="", width=40, height=11,
                                relief=tk.RAISED, justify=tk.LEFT, anchor=tk.NW)
        self.appText.grid(row=2, column=3, rowspan=2, sticky=tk.W+tk.E+tk.N,
                          padx=2)

        self.appSelect.selection_set(0)
        self.onAppSelect(None)
        
        #self.appText.insert(tk.END, )
    #self.appText.config(state=tk.DISABLED)
        #tk.Text(iframe).grid(row=0, column=1, rowspan=2)

    def initAdvanced(self):
        self.debugPrint("Setting up Advance Tab")

        iframe = Tab(self.tabFrame, "Advanced", fname='advanced')
        iframe.config(relief=tk.RAISED, borderwidth=2, width=self.widthMain,
                      height=self.heightTab)
        self.tBarFrame.add(iframe)

        canvas = tk.Canvas(iframe, bd=0, width=self.widthMain-4,
                        height=self.heightTab-4, highlightthickness=0)
        canvas.grid(row=0, column=0, columnspan=6)

        tk.Label(iframe, text="Advance").grid(row=0, column=0, columnspan=6,
                                            sticky=tk.W+tk.E+tk.N+tk.S)

    def onAppSelect(self, *args):
        self.debugPrint("App select update")
        #self.debugPrint(args)
        self.appText.config(
                        text=self.appList[int(self.appSelect.curselection()[0])
                                          ]['Description'])
    
    def launch(self):
        items = map(int, self.appSelect.curselection())
        if items:
            app = self.appList[int(self.appSelect.curselection()[0])]['FileName']
            args = self.appList[int(self.appSelect.curselection()[0])]['Args']
            self.debugPrint("Launching {}".format(app))
            self.proc.append(subprocess.Popen("./{}".format(app), cwd='./Python'))
        else:
            self.debugPrint("Nothing Selected to Launch")
            
    def readConfig(self):
        self.debugPrint("Reading Config")

        self.config = ConfigParser.SafeConfigParser()
        
        # load defaults
        try:
            self.config.readfp(open(self.configFileDefault))
        except:
            self.debugPrint("Could Not Load Default Settings File")
        
        # read the user config file
        if not self.config.read(self.configFile):
            self.debugPrint("Could Not Load User Config, One Will be Created on Exit")
        
        if not self.config.sections():
            self.debugPrint("No Config Loaded, Quitting")
            sys.exit()
        
        self.debug = self.config.getboolean('Shared', 'debug')

        try:
            f = open('Python/' + self.config.get('Update', 'versionfile'))
            self.currentVersion = f.read()
            f.close()
        except:
            pass
                
    def writeConfig(self):
        self.debugPrint("Writing Config")
        with open(self.configFile, 'wb') as configfile:
            self.config.write(configfile)

    def loadApps(self):
        self.debugPrint("Loading App List")
        try:
            with open(self.appFile, 'r') as f:
                read_data = f.read()
            f.closed
            
            self.appList = json.loads(read_data)['Apps']
        except IOError:
            self.debugPrint("Could Not Load AppList File")
            self.appList = [
                            {'id': 0,
                            'Name': 'Error',
                            'FileName': None,
                            'Args': '',
                            'Description': 'Error loading AppList file'
                            }]
            self.disableLaunch = True
# including these here as python is stupid when it comes to relative imports

BASE = tk.RAISED
SELECTED = tk.SUNKEN

# a base tab class
class Tab(tk.Frame):
    def __init__(self, master, name, fname):
        tk.Frame.__init__(self, master, name=fname)
        self.tab_name = name

# the bulk of the logic is in the actual tab bar
class TabBar(tk.Frame):
    def __init__(self, master=None, init_name=None, fname=None):
        tk.Frame.__init__(self, master, name=fname)
        self.tabs = {}
        self.buttons = {}
        self.current_tab = None
        self.init_name = init_name
    
    def show(self):
        self.pack(side=tk.TOP, expand=1, fill=tk.X)
        self.switch_tab(self.init_name or self.tabs.keys()[-1])# switch the tab to the first tab
    
    def add(self, tab):
        tab.pack_forget()									# hide the tab on init
        
        self.tabs[tab.tab_name] = tab						# add it to the list of tabs
        b = tk.Button(self, text=tab.tab_name, relief=BASE,	# basic button stuff
                      command=(lambda name=tab.tab_name: self.switch_tab(name)))	# set the command to switch tabs
        b.pack(side=tk.LEFT)											 	# pack the button to the left most of self
        self.buttons[tab.tab_name] = b											# add it to the list of buttons
    
    def delete(self, tabname):
        
        if tabname == self.current_tab:
            self.current_tab = None
            self.tabs[tabname].pack_forget()
            del self.tabs[tabname]
            self.switch_tab(self.tabs.keys()[0])
        
        else: del self.tabs[tabname]
        
        self.buttons[tabname].pack_forget()
        del self.buttons[tabname]
    
    
    def switch_tab(self, name):
        if self.current_tab:
            self.buttons[self.current_tab].config(relief=BASE)
            self.tabs[self.current_tab].pack_forget()			# hide the current tab
        self.tabs[name].pack(side=tk.BOTTOM)							# add the new tab to the display
        self.current_tab = name									# set the current tab to itself
        
        self.buttons[name].config(relief=SELECTED)					# set it to the selected style

if __name__ == "__main__":
    app = SandyLauncher()
    app.on_excute()

