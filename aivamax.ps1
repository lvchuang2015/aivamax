$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$ScriptDir\jarveepro_cli.py" @args
exit $LASTEXITCODE
