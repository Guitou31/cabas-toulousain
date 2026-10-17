# Réduit toutes les photos de app/img à 560 px de large maximum, JPEG qualité 74, et convertit les PNG en JPEG.
# Met à jour le champ "fichier" des métadonnées data/images/<id>.json quand l'extension change.
Add-Type -AssemblyName System.Drawing
$base = Split-Path -Parent $PSScriptRoot
$dir = Join-Path $base 'app\img'
$meta = Join-Path $base 'data\images'
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$ep = New-Object System.Drawing.Imaging.EncoderParameters 1
$ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), 74L
$avant = 0; $apres = 0; $n = 0
Get-ChildItem $dir -File | Where-Object { $_.Extension -match '^\.(jpg|jpeg|png|webp)$' } | ForEach-Object {
  $f = $_; $avant += $f.Length
  try { $img = [System.Drawing.Image]::FromFile($f.FullName) } catch { Write-Output "ILLISIBLE : $($f.Name)"; return }
  $w = [Math]::Min(560, $img.Width); $h = [int][Math]::Round($img.Height * $w / $img.Width)
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = 'HighQualityBicubic'; $g.SmoothingMode = 'HighQuality'; $g.PixelOffsetMode = 'HighQuality'
  $g.Clear([System.Drawing.Color]::White)   # fond blanc pour les PNG transparents
  $g.DrawImage($img, 0, 0, $w, $h); $g.Dispose(); $img.Dispose()
  $dest = Join-Path $dir ($f.BaseName + '.jpg')
  $tmp = Join-Path $dir ($f.BaseName + '.tmp.jpg')
  $bmp.Save($tmp, $codec, $ep); $bmp.Dispose()
  Remove-Item $f.FullName -Force
  Move-Item $tmp $dest -Force
  $apres += (Get-Item $dest).Length; $n++
  if ($f.Extension -ne '.jpg') {
    $mj = Join-Path $meta ($f.BaseName + '.json')
    if (Test-Path $mj) {
      $txt = [System.IO.File]::ReadAllText($mj)
      $txt = $txt -replace ('"fichier": "' + [regex]::Escape($f.Name) + '"'), ('"fichier": "' + $f.BaseName + '.jpg"')
      [System.IO.File]::WriteAllText($mj, $txt, (New-Object System.Text.UTF8Encoding $false))
    }
  }
}
Write-Output ("{0} images : {1:N0} Ko -> {2:N0} Ko" -f $n, ($avant/1KB), ($apres/1KB))
