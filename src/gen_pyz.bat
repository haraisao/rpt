@setlocal
@call %~d0\local\Python37\PyEnv.bat
python -m zipapp rpt -m "rpt:main"
@endlocal