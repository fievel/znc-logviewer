# vim: ff=unix
import znc
import os
import sys
import re
import glob

sys.dont_write_bytecode = False


class logviewer(znc.Module):
    description = "View and search logs directly from IRC client"
    module_types = [znc.CModInfo.NetworkModule]

    def OnLoad(self, args, message):
        try:
            self.__cmdDispatcher = LogViewerCommandDispatcher(self)
            self.__cmdDispatcher.AddCommand(LogCatCommand(self))
            self.__cmdDispatcher.AddCommand(LogGrepCommand(self))
            self.__cmdDispatcher.AddCommand(LogDatesCommand(self))
            self.__cmdDispatcher.AddCommand(LogWindowsCommand(self))
        except Exception as e:
            message.s = "Error: {0}".format(e)
            return False
        return True

    def OnModCommand(self, line):
        self.__cmdDispatcher.Dispatch(line)
        return True


class LogViewerCommandDispatcher(object):
    def __init__(self, module):
        self.__module = module
        self.__commands = dict()

    def AddCommand(self, command):
        isinstance(command, AbstractLogViewerCommand)
        if command.GetName().lower() in self.__commands:
            raise NameError("command already registered")
        self.__commands[command.GetName().lower()] = command

    def Dispatch(self, line):
        args = line.split()
        if args[0].lower() in self.__commands.keys():
            cmdArgs = None
            if len(args) > 1:
                cmdArgs = args[1:]
            self.__commands[args[0].lower()].Perform(cmdArgs)
        elif args[0].lower() == "help":
            self.__module.PutModule("View and search logs.")
            self.__module.PutModule("---------------------")
            self.__module.PutModule("Available commands: ")
            for aCmd in self.__commands.values():
                self.__module.PutModule(aCmd.Describe())
            self.__module.PutModule("Use \"<command> help\" for usage info.")
        else:
            self.__module.PutModule("Command not found: {0}".format(args[0]))
            self.__module.PutModule("Use Help for list of available commands")


class IrcLogPathBuilder(object):
    def __init__(self, network, user):
        self.__network = network
        self.__user = user

    def __getBasePath(self):
        return os.path.join(os.path.expanduser("~"),
                            ".znc",
                            "users",
                            self.__user,
                            "moddata",
                            "log",
                            self.__network)

    def GetLogPath(self, window, date):
        return os.path.join(self.__getBasePath(),
                            window,
                            "{0}.log".format(date))

    def GetLogsDates(self, window):
        aPath = os.path.join(self.__getBasePath(),
                             window,
                             "*.log")
        return [os.path.basename(fn).replace(".log", "") for fn in glob.glob(aPath)]

    def GetWinList(self):
        aPath = os.path.join(self.__getBasePath(), "*")
        return [os.path.basename(fn) for fn in glob.glob(aPath) if os.path.isdir(fn)]


class IrcLog(object):
    def __init__(self, network, user, window, date):
        self.__network = network
        self.__user = user
        self.__window = window
        self.__date = date
        aPathBuilder = IrcLogPathBuilder(network, user)
        self.__path = aPathBuilder.GetLogPath(window, date)
        self.__file = None

    def GetNetwork(self):
        return self.__network

    def GetUser(self):
        return self.__user

    def GetWindow(self):
        return self.__window

    def GetDate(self):
        return self.__date

    def GetPath(self):
        return self.__path

    def Exists(self):
        return os.path.isfile(self.GetPath())

    def __enter__(self):
        self.__file = open(self.GetPath(), 'r',
                           encoding=sys.getdefaultencoding(),
                           errors='replace')
        return self.__file

    def __exit__(self, type, value, traceback):
        if self.__file is not None:
            self.__file.close()


class AbstractLogViewerCommand(object):
    def __init__(self, module):
        self.__command = ""
        self.__description = ""
        self.__argsStr = ""
        self.__module = module

    def _setCommand(self, cmd):
        self.__command = cmd

    def _setDescription(self, desc):
        self.__description = desc

    def _setArgumentString(self, args):
        self.__argsStr = args

    def GetNetwork(self):
        return self.__module.GetNetwork().GetName()

    def GetUser(self):
        return self.__module.GetUser().GetUserName()

    def GetName(self):
        return self.__command

    def GetDescription(self):
        return self.__description

    def GetArgumentString(self):
        return self.__argsStr

    def Print(self, string):
        self.__module.PutModule(string)

    def PrintErr(self, string):
        self.Print("ERROR: {0}".format(string))

    def Describe(self):
        return "{0} - {1}".format(self.GetName(), self.GetDescription())

    def Help(self):
        self.Print("{0} {1}".format(self.GetName(), self.GetArgumentString()))
        self.Print(self.GetDescription())

    def Perform(self, args):
        if args is not None and len(args) > 0 and args[0].lower() == "help":
            self.Help()
            return
        if args is None:
            args = []
        self._DoPerform(args)

    def _DoPerform(self, args):
        raise NotImplementedError("")


class LogCatCommand(AbstractLogViewerCommand):
    def __init__(self, module):
        super().__init__(module)
        self._setCommand("LogCat")
        self._setArgumentString("<window> <date>")
        self._setDescription(
            "View log file for window and date (current network).")

    def __showLog(self, window, date):
        aIrcLog = IrcLog(self.GetNetwork(),
                         self.GetUser(),
                         window,
                         date)
        if not aIrcLog.Exists():
            self.PrintErr("No such log file for {0} on {1} ({2})".format(
                window, date, aIrcLog.GetPath()))
            return
        self.Print("Content of {0}:".format(aIrcLog.GetPath()))
        try:
            with aIrcLog as f:
                for line in f:
                    self.Print(line)
        except Exception as e:
            self.PrintErr(str(e))
            return

    def _DoPerform(self, args):
        if len(args) != 2:
            self.Help()
            return
        aWindow = args[0]
        aDate = args[1]
        self.__showLog(aWindow, aDate)


class LogGrepCommand(AbstractLogViewerCommand):
    def __init__(self, module):
        super().__init__(module)
        self._setCommand("LogGrep")
        self._setArgumentString("<window> <date> <regex>")
        self._setDescription(
            "Grep log file for window and date (current network) with regex.")

    def __grepLog(self, window, date, regex):
        aIrcLog = IrcLog(self.GetNetwork(),
                         self.GetUser(),
                         window,
                         date)
        if not aIrcLog.Exists():
            self.PrintErr("No such log file for {0} on {1} ({2})".format(
                window, date, aIrcLog.GetPath()))
            return
        self.Print("Content of {0} matching {1}:".format(aIrcLog.GetPath(),
                                                         regex))
        try:
            aRegex = re.compile(regex)
            with aIrcLog as f:
                for line in f:
                    if aRegex.search(line) is not None:
                        self.Print(line)
        except Exception as e:
            self.PrintErr(str(e))
            return

    def _DoPerform(self, args):
        if len(args) != 3:
            self.Help()
            return
        aWindow = args[0]
        aDate = args[1]
        aRegex = args[2]
        self.__grepLog(aWindow, aDate, aRegex)


class LogDatesCommand(AbstractLogViewerCommand):
    def __init__(self, module):
        super().__init__(module)
        self._setCommand("LogDates")
        self._setArgumentString("<window>")
        self._setDescription(
            "List all available dates for window.")

    def _DoPerform(self, args):
        if len(args) != 1:
            self.Help()
            return
        aWindow = args[0]
        aPathBuilder = IrcLogPathBuilder(self.GetNetwork(), self.GetUser())
        aDates = aPathBuilder.GetLogsDates(aWindow)
        if len(aDates) > 0:
            self.Print(
                "List of all available log date for window {0}:".format(aWindow))
            for d in sorted(aDates):
                self.Print(d)
        else:
            self.PrintErr("No such logs for window {0}".format(aWindow))


class LogWindowsCommand(AbstractLogViewerCommand):
    def __init__(self, module):
        super().__init__(module)
        self._setCommand("LogWindows")
        self._setArgumentString("")
        self._setDescription(
            "List all available windows.")

    def _DoPerform(self, args):
        if len(args) != 0:
            self.Help()
            return
        aPathBuilder = IrcLogPathBuilder(self.GetNetwork(), self.GetUser())
        aWins = aPathBuilder.GetWinList()
        if len(aWins) > 0:
            self.Print(
                "List of all available windows:")
            for w in sorted(aWins):
                self.Print(w)
        else:
            self.PrintErr("No such windows logs")
