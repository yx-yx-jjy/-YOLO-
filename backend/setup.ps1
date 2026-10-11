$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$python312 = 'C:\Users\admin\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe'

if (-not (Test-Path -LiteralPath $python312)) {
  throw 'Python 3.12 runtime was not found.'
}

$venvPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
  & $python312 -m venv (Join-Path $backendRoot '.venv')
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $backendRoot 'requirements.txt')

$hasNvidia = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if ($hasNvidia) {
  $cudaReady = & $venvPython -c "import torch; print('1' if torch.cuda.is_available() else '0')"
  if ($cudaReady -ne '1') {
    Write-Host 'Installing the CUDA 12.6 PyTorch build for the NVIDIA GPU...'
    & $venvPython -m pip install --upgrade torch==2.14.0+cu126 torchvision==0.29.0+cu126 --index-url https://download.pytorch.org/whl/cu126
  }
}

