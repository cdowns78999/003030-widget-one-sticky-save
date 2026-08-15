' Claude Token Widget — silent startup launcher (no console flash)
' Dumps latest widget.html/poll.py from the local GitHub clone before firing.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\chad\claude-token-widget"
sh.Run "cmd /c sync_from_repo.bat", 0, True
sh.Run "pythonw.exe poll.py", 0, False
WScript.Sleep 2500
sh.Run "chrome --app=http://127.0.0.1:8743/widget.html --window-size=380,380", 1, False
