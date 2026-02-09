#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Applies CSP meta tag to frontend index.html

.DESCRIPTION
    STATUS: Ready for use when frontend is rebuilt in OmniAI/frontend

    This script adds the CSP meta tag to the frontend's index.html file
    inside <head> before any <script> tags.

    DO NOT RUN until frontend exists at specified path.

.PARAMETER FrontendPath
    Path to the frontend repository (default: ../../omniplexity.github.io)

.PARAMETER Mode
    CSP mode: 'development' (allows https:) or 'production' (specific domain)

.PARAMETER ApiDomain
    API domain for production mode (e.g., 'api.yourdomain.com')

.EXAMPLE
    .\apply_csp.ps1 -Mode development

.EXAMPLE
    .\apply_csp.ps1 -Mode production -ApiDomain "chat.example.com"
#>

param(
    [string]$FrontendPath = "../../omniplexity.github.io",
    [ValidateSet('development', 'production')]
    [string]$Mode = "development",
    [string]$ApiDomain = ""
)

$ErrorActionPreference = "Stop"

# Resolve the frontend path
$FullPath = Resolve-Path $FrontendPath -ErrorAction SilentlyContinue
if (-not $FullPath) {
    Write-Error "Frontend path not found: $FrontendPath"
    exit 1
}

$IndexPath = Join-Path $FullPath "index.html"
if (-not (Test-Path $IndexPath)) {
    Write-Error "index.html not found at: $IndexPath"
    exit 1
}

# Read the current index.html
$Content = Get-Content $IndexPath -Raw

# Check if CSP already exists
if ($Content -match '<meta http-equiv="Content-Security-Policy') {
    Write-Warning "CSP meta tag already exists in index.html"
    Write-Host "To re-apply, first remove the existing CSP meta tag."
    exit 0
}

# Build CSP based on mode
if ($Mode -eq "production") {
    if ([string]::IsNullOrEmpty($ApiDomain)) {
        Write-Error "ApiDomain is required for production mode"
        exit 1
    }
    $ConnectSrc = "connect-src 'self' https://$ApiDomain;"
} else {
    $ConnectSrc = "connect-src 'self' https:;"
}

$CspTag = @"
    <meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  img-src 'self' data: blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self';
  $ConnectSrc
">
"@

# Find the position to insert (before first script tag)
$ScriptPattern = '<script'
$ScriptMatch = [regex]::Match($Content, $ScriptPattern)

if ($ScriptMatch.Success) {
    $InsertPosition = $ScriptMatch.Index
    $BeforeScripts = $Content.Substring(0, $InsertPosition)
    $AfterScripts = $Content.Substring($InsertPosition)

    $NewContent = $BeforeScripts.TrimEnd() + "`n`n$CspTag`n`n" + $AfterScripts
} else {
    # No script tags found, insert after <head>
    $HeadMatch = [regex]::Match($Content, '</head>', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($HeadMatch.Success) {
        $InsertPosition = $HeadMatch.Index
        $BeforeHeadEnd = $Content.Substring(0, $InsertPosition)
        $AfterHeadEnd = $Content.Substring($InsertPosition)
        $NewContent = $BeforeHeadEnd.TrimEnd() + "`n`n$CspTag`n`n" + $AfterHeadEnd
    } else {
        # Just append before </html>
        $HtmlMatch = [regex]::Match($Content, '</html>', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($HtmlMatch.Success) {
            $InsertPosition = $HtmlMatch.Index
            $BeforeHtmlEnd = $Content.Substring(0, $InsertPosition)
            $AfterHtmlEnd = $Content.Substring($InsertPosition)
            $NewContent = $BeforeHtmlEnd.TrimEnd() + "`n`n$CspTag`n`n" + $AfterHtmlEnd
        } else {
            Write-Error "Could not find insertion point in index.html"
            exit 1
        }
    }
}

# Backup original
$BackupPath = "$IndexPath.backup"
Copy-Item $IndexPath $BackupPath
Write-Host "Backed up original to: $BackupPath"

# Write new content
$NewContent | Set-Content $IndexPath -NoNewline
Write-Host "CSP meta tag applied to: $IndexPath"
Write-Host ""
Write-Host "Verification checklist:"
Write-Host "1. Open browser DevTools (F12)"
Write-Host "2. Check Console for CSP violations"
Write-Host "3. Verify API calls still work (Network tab)"
Write-Host "4. Test login/auth flow"
