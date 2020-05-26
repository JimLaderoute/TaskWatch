#/****************************************************************
#   Python File: taskWatch.py
#   Description: Application to assist in keeping track how much
#     time has been spent on various tasks per day.
#
#     History:
#
#      Date       Programmer        Description
#      ---------- ---------------- ----------------------------
#      11/06/2016 James Laderoute  Created
#      05/23/2020 James Laderoute  Read,Save,SaveConfig,Header for Title,LargestAvailableIdNumber,
#                 capture WM_DELETE_WINDOW event using function exitApplication which will update the config info and
#                 will write out all the current tasks. Select item now changes Active field from NotActive to Active.
#                 Added balloon messages for the buttons. Time is now fully working. Refactored a number of function
#                 names so they make more sense.
#
# ****************************************************************
#  Copyright (c) James Laderoute, 2016, 2020
# 
#  This unpublished material is proprietary to James Laderoute.
#  All rights reserved. The methods and
#  techniques described herein are considered trade secrets
#  and/or confidential. Reproduction or distribution, in whole
#  or in part, is forbidden except by express written permission
#  of James Laderoute.
# ****************************************************************
#
# TODO
# ++ Start/Stop Timer
# -- add threaded timer to go off every second [done]
# -- update the daily time in the gui [done]
# -- save+read the daily time [done - 2020-05-24]
#
# ++ Sort by Header Column
# ++ Hide Rows & Unhide Rows
# ++ Show Hidden Rows - Toggle Button
# ++ Implement +1hr, -1hr adjustment buttons [done 2020-05-24]
# ++ Update and show total Daily Time Spent
# ++ Implement <<, >> buttons  (pan thru time)
# ++ Allow user to Edit the Task Name cell
# ++ Allow more than one user account
# ++ Add a report generator (save info in JSON format)

import os
from tkinter import *
import Pmw
import threading
from tkinter import ttk
from datetime import date
from datetime import time
from datetime import datetime

releaseVersion = "Beta 1.1"

root = Tk()                     # this is the root widget of all other GUI widgets in the application
textEntryWidget = 0             # this is the text text entry widget used to enter TEXT for a new task
treeViewWidget = 0              # this is the treeView widget
timerObj = None                 # this is the threaded timer object we use to update active tasks
LargestAvailableIdNumber = 0    # this keeps track of the last id number; we use unique id numbers per task
timeDict = {}                   # this dictionary keeps track of n seconds applied to each task item, we need this so
                                # we can keep track of fractional seconds. This fractional second is needed when we are
                                # sharing a time unit among multiple active/selected tasks.

def exitApplication():
  global root
  global timerObj
  timerObj.cancel()
  saveTasks()
  root.destroy()

def main():
  global textEntryWidget
  global treeViewWidget
  global root
  global balloon

  theCurrentWorkingDir = os.getcwd()
  print("Your directory is %s\n" % theCurrentWorkingDir)
  if not os.path.isdir("user") :
    os.mkdir('user')

  totalTime = "Total: ##:##:##"
  #root = Tk()
  root.protocol("WM_DELETE_WINDOW", exitApplication)
  root.title("Task Watcher " + releaseVersion )
  root.option_add('*tearOff', False)  # don't allow tear-off menus

  Pmw.initialise()
  balloon = Pmw.Balloon(root)

  # --------- Create a standard MenuBar ----------------
  
  menubar = Menu(root)
  root.config(menu = menubar)
  file = Menu(menubar)
  edit = Menu(menubar)
  help_ = Menu(menubar)
  menubar.add_cascade( menu = file, label = "File")
  menubar.add_cascade( menu = edit, label = "Edit")
  menubar.add_cascade( menu = help_, label = "Help")
  file.add_command(label = 'New', command = lambda: print('TODO: New File'))
  file.add_separator()
  file.add_command(label = 'Open...', command = lambda: print('TODO: Open File...'))
  file.add_command(label = 'Save', command = lambda: saveTasks())
  file.add_command(label = 'Exit', command = lambda: exitApplication())

  file.entryconfig('New', accelerator = 'Ctrl + N') # does not setup event, only puts text in btn
  file.entryconfig('Open...', accelerator = 'Ctrl + O')
  file.entryconfig('Save', accelerator = 'Ctrl + S')
  file.entryconfig('Exit', accelerator = 'Ctrl + Z')
  
  root.columnconfigure(0, weight=1)
  root.rowconfigure(0, weight=1)
  
  # ---------- Create Tree that displays all tasks
  treeViewWidget = ttk.Treeview(root)
  vsb = ttk.Scrollbar(root, orient="vertical", command=treeViewWidget.yview)
  vsb.grid(row=0,column=1, sticky=N+S)
  treeViewWidget.configure(yscrollcommand=vsb.set)

  columnNames = {'IdNum' : 16, 'Category' : 60, 'Active': 50, 'Hidden': 50, 'Created':100, 'Today': 100}  # dictionary
  treeViewWidget["columns"] = ("IdNum", "Category", "Active", "Hidden", "Created", "Today")
  for name,colWidth in columnNames.items() :
    treeViewWidget.column(name, width=colWidth)
    treeViewWidget.heading(name, text=name)
  treeViewWidget.heading('#0', text='Task Name')

  treeViewWidget.grid(row=0, column=0, sticky=N + E + W + S)
  treeViewWidget.bind('<<TreeviewSelect>>', treeCallbackWhenSelectingATreeViewRow)
  #treeViewWidget.config(selectmode = 'browse') # this allows only one item to be selected at a time

  # --------- Create buttons on bottom
  fr2 = Frame(root)
  for i in range(10):
    fr2.columnconfigure(i, weight=1)

  fr2.grid(row=1,column=0,sticky=W+E)

  createButtonBalloonWidget(fr2, "Stop", "Stop All Timers", 0, 0)
  createButtonBalloonWidget(fr2, "Delete", "Delete Selected Tasks", 0, 1)
  createButtonBalloonWidget(fr2, "Hide", "Hide Selected Tasks", 0, 2)
  createButtonBalloonWidget(fr2, "+1hr", "Add one hour to selected tasks", 0, 3)
  createButtonBalloonWidget(fr2, "-1hr", "Subtract one hour from selected tasks", 0, 4)
  createButtonBalloonWidget(fr2, "<<", "Goto Previous Day Tasks", 0, 5)
  createButtonBalloonWidget(fr2, ">>", "Goto Next Day Tasks", 0, 6)
  
  Label(fr2, text=totalTime, textvariable=totalTime ).grid(row=0, column=i, sticky=W)

  # ---------- Create new task textEntryWidget field
  fr3 = Frame(root)
  for i in range(10):
    fr3.columnconfigure(i, weight=1)
    
  fr3.grid(row=2,column=0,sticky=W+E+S+N)
  createButtonBalloonWidget(fr3, "New>", "Create a new task", 0, 0)
  textEntryWidget = Entry(fr3, width=40)
  textEntryWidget.grid(row=0, column=1, sticky=W + E)
  textEntryWidget.bind("<Return>", keypressCallbackForCreatingNewTask)

  # --------- read in created tasks

  readTasks()

  # --------- Start the main timer; this updates the time field of tasks
  timerCallbackPerSecond()
#  timer = threading.Timer(1.0, timerCallbackPerSecond)
#  timer.start()


  # --------- go into main graphics loop now
  root.mainloop()


# -------- FUNCTIONS ----------------------------
def timerCallbackPerSecond():
  global treeViewWidget
  global timerObj
  global timeDict

  counts = len(treeViewWidget.selection())
  # Now we want to look at every selected task (these are active) and update it's time clock
  for itemId in treeViewWidget.selection() :
    value = treeViewWidget.set(itemId, column="#3")
    if value == "Active" :
      try:
        nSeconds = timeDict[itemId]
        nSeconds = nSeconds + 1.0 / counts
        timeDict[itemId] = nSeconds
        timevalue = convertSecondsToHMS( nSeconds )
        treeViewWidget.set(itemId, column="#6", value=timevalue)
      except KeyError:
        print("key itemId not there ")
        print(itemId)
  # To keep the timer going we have to start it again
  # or I need to read more about timer.start()
  timerObj = threading.Timer(1.0, timerCallbackPerSecond)
  timerObj.start()

def createButtonBalloonWidget(widget, name, balloonText, rowvalue, columnvalue):
  global balloon
  b=Button(widget, text=name, command=lambda: buttonCallbackWhenUserClicksAButton(name))
  b.grid(row=rowvalue, column=columnvalue, sticky=W+E)
  balloon.bind(b, balloonText)

def convertSecondsToHMS( nSeconds : float ) -> str :
  lhours =  int(nSeconds) // 3600
  lminutes = ( int(nSeconds) - lhours*3600) // 60
  lseconds = int(nSeconds)  - int(lminutes * 60) - int(lhours * 3600)
  return "%d:%d:%d" % (lhours,lminutes,lseconds)

def deactivateAllTimers():
  global treeViewWidget
  for itemId in treeViewWidget.get_children() :
    changeTaskActiveToNotActive(itemId)

def changeTaskActiveToNotActive(selectId):
  global treeViewWidget
  treeViewWidget.set(selectId, column="#3", value="NotActive")

def changeTaskNotActiveToActive(selectId):
  global treeViewWidget
  treeViewWidget.set(selectId, column="#3", value="Active")

def saveConfig():
  global LargestAvailableIdNumber
  try:
    with open('user/myconfig.txt', 'w') as f:
      line = "LargestAvailableIdNumber:" + str(LargestAvailableIdNumber) + "\n"
      f.write(line)
      f.close()
  except IOError as e:
    print("You file could not be opened for write. (%s)\n" % e)


#++
# The file it reads is a plain text file that contains one line per task
# each line has the following syntax. White space is ignored. And you
# can have comments in the file that get ignored, just place '#' in column 0
#
# TITLE:The title goes here
# IDNUM: Unique Identifier Per Task
# CATEGORY:ANY CATEGORY
# CREATED: date-string
# HIDDEN: TRUE|FALSE
#
# TITLE: Next Task Title
# IDNUM: Unique Identifier Per Task
# CATEGORY:ANY CATEGORY
# CREATED: date-string
# HIDDEN: TRUE|FALSE

def saveTasks():
  global treeViewWidget

  # Always save updated configurations when we also save things
  saveConfig()

  x = open('user/filename.txt', 'w') # open file for write
  for itemId in treeViewWidget.get_children():
    line = "\nTITLE:^:" + treeViewWidget.item(itemId, "text") + "\n"
    x.write(line)
    taskIdNumber = int( treeViewWidget.set(itemId,"#1") )
    fields = treeViewWidget.set(itemId)
    for part in fields:
      if "ACTIVE" != part.upper() and "TODAY" != part.upper() :
        line = part.upper() + ':^:' + fields[part] + '\n'
        x.write(line)
      elif "TODAY" == part.upper() :
        saveTodaysTime(itemId, taskIdNumber)
  x.close()

def readTodaysTime(itemId, taskIdNumber : int) :
  global timeDict
  global treeViewWidget

  dirName = "user/{}".format(taskIdNumber)
  if os.path.isdir(dirName) :
    fname = "user/{}/{}_sec.txt".format(taskIdNumber, date.today())
    if os.path.isfile(fname) :
      try:
        rf = open(fname, 'r')
        lineSeconds = rf.readline()
        lineSeconds = lineSeconds.strip()
        timeDict[itemId] = float(lineSeconds)
        treeViewWidget.set(itemId, column="#6", value=convertSecondsToHMS(float(lineSeconds)))
        rf.close()
      except IOError as e:
        print("Problem reading time info from file. (%s)\n" % e)

def saveTodaysTime(itemId, taskIdNumber : int) :
  global timeDict

  if timeDict[itemId] >= 0.9 :
    dirName = "user/{}".format(taskIdNumber)
    if not os.path.isdir(dirName) :
      os.mkdir(dirName)

    fname = "user/{}/{}_sec.txt".format(taskIdNumber, date.today())
    try:
      wf = open(fname, 'w')
      wf.write(str(timeDict[itemId]))
      wf.close()
    except IOError as e:
      print("Problem saving time info for task id. (%s)\n" % e)

def readTasks():
  global treeViewWidget
  global LargestAvailableIdNumber
  global timeDict

  title=""
  idnum="0"
  category=""
  createdDate=""
  isActive="No"
  name=""
  value=""

  theDate = date.today()

  # We store the highest id number into a file, read it in if it exists and use that for out LargestAvailableIdNumber
  try:
    with open('user/myconfig.txt', 'r') as f:
      for line in f:
        line = line.strip()
        if "" == line or '#' == line[0]:
          continue
        name, value = line.split(":",2)
        if name=="LargestAvailableIdNumber":
          LargestAvailableIdNumber = int(value)
      f.close()
  except IOError as e:
    print("Your file could not be opened. (%s)\n" % e)

  print("now opening filename.txt\n")
  try:
    with open('user/filename.txt', 'r') as f:
      for line in f:
        # chomp off whitespace from front and end of string
        line = line.strip()
        # skip blank lines or comments
        if "" == line or '#' == line[0]:
          continue
        # split the line into NAME:value
        name, value = line.split(":^:", 2)
        if name=="TITLE":
          if title!="" : # a previous task has been read in process it
            iid = addTaskToTreeViewList(title=title, idnum=idnum, cat=category, createDate=createdDate)
            LargestAvailableIdNumber = max(LargestAvailableIdNumber, int(idnum))
            readTodaysTime(iid, idnum)
          title=value
          idnum="0"
          category=""
          hidden=""
          createdDate=""
        elif name=="IDNUM":
          idnum=value
        elif name=="CATEGORY":
          category=value
        elif name=="CREATED":
          createdDate=value
        elif name=="HIDDEN":
          hidden=value
      f.close()
  except (OSError, IOError) as exc:
      print("You file could not be opened (%s)\n" % exc)

  if title != "":  # a previous task has been read in process it
    iid = addTaskToTreeViewList(title=title, idnum=idnum, cat=category, createDate=createdDate)
    LargestAvailableIdNumber = max(LargestAvailableIdNumber, int(idnum))
    readTodaysTime(iid, idnum)
    treeViewWidget.focus(iid)

# -------- CALLBACKS ----------------------------

# This callback is invoked when the user clicks one of the
# buttons such as: Stop, Delete, etc...
#
def buttonCallbackWhenUserClicksAButton(param):
  global treeViewWidget
  activeSel= treeViewWidget.selection()
  if activeSel :
    if param == "Stop" :
      treeViewWidget.selection_remove(activeSel)
      deactivateAllTimers()
    elif param == "Delete" :
      treeViewWidget.delete(activeSel)
    elif param == "Hide" :
      print("TODO: ", param)
    elif param == "+1hr" :
      for iid in activeSel:
        timeDict[iid] = timeDict[iid] + 3600.0
    elif param == "-1hr" :
      for iid in activeSel:
        timeDict[iid] = timeDict[iid] - 3600.0
        if timeDict[iid] < 0.0 :
          timeDict[iid] = 0.0
  else:
    if param == ">>" :
      print("TODO: ",param)
    elif param == "<<" :
      print("TODO: ",param)
    elif param == "New>" :
      buttonCallbackForCreatingNewTask()

def addTaskToTreeViewList(title="NoTitle", idnum="id", cat="NoCategory", isactive="NotActive", ishidden="NotHidden", createDate="yyyy:mm:dd", todayTime="hh:mm:ss"):
    global treeViewWidget
    global LargestAvailableIdNumber
    global timeDict

    if createDate=="yyyy:mm:dd":
      createDate = date.today()

    if todayTime=="hh:mm:ss":
        todayTime="00:00:00"
    if idnum=="id":
      LargestAvailableIdNumber = LargestAvailableIdNumber + 1
      idnum = str(LargestAvailableIdNumber)

    item = treeViewWidget.insert("", 'end', text=title, values=(idnum, cat, isactive, ishidden, createDate, todayTime))

    timeDict[item] = 0.0  # number of seconds

    return item

#
# When user clicks <<RETURN>> we call this function.
# this function adds a new Task to the list
#
def keypressCallbackForCreatingNewTask(event):
  global treeViewWidget
  global textEntryWidget
  value = textEntryWidget.get()
  if value :
    item = addTaskToTreeViewList(title=value)
    treeViewWidget.focus(item)
    activeSel = treeViewWidget.selection()
    if activeSel :
      treeViewWidget.selection_remove(activeSel)
    treeViewWidget.selection_add(item)
    textEntryWidget.delete(0, END)

#
# When user clicks on the "New>" button we call this function.
# this function adds a new Task to the list
#
def buttonCallbackForCreatingNewTask():
  global treeViewWidget
  global textEntryWidget

  value = textEntryWidget.get()
  if value :
    item = addTaskToTreeViewList(title=textEntryWidget.get())
    treeViewWidget.focus(item)

    activeSel = treeViewWidget.selection()
    if activeSel :
      treeViewWidget.selection_remove(activeSel)
    treeViewWidget.selection_add(item)
    textEntryWidget.delete(0, END)

#
# When user clicks on an item in the treeViewWidget, this is called
# We use this function to activate the Task's timer
#
def treeCallbackWhenSelectingATreeViewRow(event):
  global treeViewWidget
  if treeViewWidget.selection() :
    # for each item NOT selected: item:Active=NotActive
    # for each item selected: item:Active=Active
    deactivateAllTimers()
    for selectId in treeViewWidget.selection() :
      changeTaskNotActiveToActive(selectId)

if __name__ == "__main__":
  main()


