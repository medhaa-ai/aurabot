Set sh = CreateObject("WScript.Shell")
sh.Environment("Process")("ELECTRON_RUN_AS_NODE") = ""
sh.Environment("Process")("ELECTRON_NO_ASAR") = ""
sh.Run """C:\Users\medha\AuraBot\dist\win-unpacked\AuraBot.exe""", 0, False
