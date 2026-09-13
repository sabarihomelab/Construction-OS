param(
    [string]$GradleVersion = '9.6.0'
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$mobileRoot = Join-Path $PSScriptRoot 'apps\mobile'
if (-not (Test-Path $mobileRoot)) {
    throw 'Android project was not found at apps\mobile.'
}

function Ensure-Java {
    $java = Get-Command java -ErrorAction SilentlyContinue
    if ($java) {
        return
    }

    $androidStudioJbr = Join-Path $env:ProgramFiles 'Android\Android Studio\jbr'
    $javaExe = Join-Path $androidStudioJbr 'bin\java.exe'
    if (Test-Path $javaExe) {
        $env:JAVA_HOME = $androidStudioJbr
        $env:Path = "$androidStudioJbr\bin;$env:Path"
        return
    }

    throw 'Java was not found. Install Android Studio first, then run this script again.'
}

Ensure-Java

$stateRoot = Join-Path $PSScriptRoot '.construction-os\android-bootstrap'
$zipPath = Join-Path $stateRoot "gradle-$GradleVersion-bin.zip"
$gradleHome = Join-Path $stateRoot "gradle-$GradleVersion"
$generatorRoot = Join-Path $stateRoot 'wrapper-generator'
$gradleBat = Join-Path $gradleHome 'bin\gradle.bat'

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null

if (-not (Test-Path $gradleBat)) {
    $url = "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip"
    Write-Host "Downloading Gradle $GradleVersion from the official Gradle distribution..."
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing

    Write-Host 'Extracting Gradle...'
    Expand-Archive -Path $zipPath -DestinationPath $stateRoot -Force
}

Remove-Item $generatorRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $generatorRoot -Force | Out-Null
Set-Content -Path (Join-Path $generatorRoot 'settings.gradle.kts') -Encoding UTF8 -Value 'rootProject.name = "construction-os-wrapper-bootstrap"'
Set-Content -Path (Join-Path $generatorRoot 'build.gradle.kts') -Encoding UTF8 -Value ''

Write-Host "Generating Gradle $GradleVersion wrapper..."
Push-Location $generatorRoot
try {
    & $gradleBat wrapper --gradle-version $GradleVersion --distribution-type bin --no-daemon
    if ($LASTEXITCODE -ne 0) {
        throw 'Gradle wrapper generation failed.'
    }
}
finally {
    Pop-Location
}

$wrapperDir = Join-Path $mobileRoot 'gradle\wrapper'
New-Item -ItemType Directory -Path $wrapperDir -Force | Out-Null
Copy-Item (Join-Path $generatorRoot 'gradlew') (Join-Path $mobileRoot 'gradlew') -Force
Copy-Item (Join-Path $generatorRoot 'gradlew.bat') (Join-Path $mobileRoot 'gradlew.bat') -Force
Copy-Item (Join-Path $generatorRoot 'gradle\wrapper\gradle-wrapper.jar') (Join-Path $wrapperDir 'gradle-wrapper.jar') -Force
Copy-Item (Join-Path $generatorRoot 'gradle\wrapper\gradle-wrapper.properties') (Join-Path $wrapperDir 'gradle-wrapper.properties') -Force

Write-Host ''
Write-Host 'Construction OS Android Gradle wrapper is ready.' -ForegroundColor Green
Write-Host "Gradle version: $GradleVersion"
Write-Host "Android project: $mobileRoot"
Write-Host ''
Write-Host 'Next:'
Write-Host '  1. Close and reopen Android Studio.'
Write-Host '  2. Open apps\mobile.'
Write-Host '  3. Use JDK 17 for the Gradle JVM.'
Write-Host '  4. Sync Project with Gradle Files.'
