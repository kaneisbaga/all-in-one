@echo off
if "%1" == "h" goto begin
mshta vbscript:createobject("wscript.shell").run("""%~f0"" h",0)(window.close)&&exit
:begin
cd /d "%~dp0"
start "" pythonw "%~dp0gui.py"
exit
