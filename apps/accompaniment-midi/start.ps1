$project = $PSScriptRoot
$python = Join-Path $project '../../work/venv/Scripts/python.exe'
& $python (Join-Path $project 'app.py')
