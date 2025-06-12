# Tập lệnh PowerShell để chạy Game2Text với quyền admin
$pythonPath = "E:\GITHUB_SPACE\Game2Text\venv\Scripts\python.exe"

# Tạo một quy trình PowerShell mới với quyền nâng cao
Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -NoExit -Command `"cd E:\GITHUB_SPACE\Game2Text; & '$pythonPath' game2text.py`"" -Verb RunAs
