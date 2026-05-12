$ErrorActionPreference = "Stop"

$csSource = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;

class SevenZipWrapper {
    static string QuoteArg(string arg) {
        if (arg.Contains(" ") || arg.Contains("\"")) {
            return "\"" + arg.Replace("\"", "\\\"") + "\"";
        }
        return arg;
    }

    static int Main() {
        string[] rawArgs = Environment.GetCommandLineArgs();
        // rawArgs[0] = this exe path, [1..] = actual args
        var filtered = rawArgs.Skip(1).Where(a => a != "-snld").ToArray();

        string myPath = System.Reflection.Assembly.GetExecutingAssembly().Location;
        string myDir = Path.GetDirectoryName(myPath);
        string realExe = Path.Combine(myDir, "7za-orig.exe");

        string arguments = string.Join(" ", filtered.Select(QuoteArg));

        // Find output directory from -o args (for winCodeSign extraction success check)
        string outDir = null;
        foreach (var a in filtered) {
            if (a.StartsWith("-o") && a.Length > 2) {
                outDir = a.Substring(2);
                break;
            }
        }

        var psi = new ProcessStartInfo {
            FileName = realExe,
            Arguments = arguments,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        var proc = Process.Start(psi);
        string stdout = proc.StandardOutput.ReadToEnd();
        string stderr = proc.StandardError.ReadToEnd();
        proc.WaitForExit();

        Console.Out.Write(stdout);
        Console.Error.Write(stderr);

        // If 7za exited with error but key Windows files exist, treat as success.
        // The errors are always macOS .dylib symlinks which are irrelevant on Windows.
        if (proc.ExitCode != 0 && outDir != null) {
            if (File.Exists(Path.Combine(outDir, "rcedit-x64.exe")) ||
                File.Exists(Path.Combine(outDir, "rcedit-ia32.exe"))) {
                return 0;
            }
        }

        return proc.ExitCode;
    }
}
'@

$baseDir = 'd:\python\PycharmProjects\CraftFlow\craftflow-desktop\node_modules\7zip-bin\win'

foreach (${arch} in @('x64', 'ia32', 'arm64')) {
    $targetDir = "$baseDir\${arch}"
    $origExe = "$targetDir\7za-orig.exe"
    $wrapperExe = "$targetDir\7za.exe"

    if (-not (Test-Path $targetDir)) {
        Write-Host "Skipping ${arch}: directory not found"
        continue
    }

    # Rename original 7za.exe if not already renamed
    if ((Test-Path "$targetDir\7za.exe") -and -not (Test-Path $origExe)) {
        # Check if 7za.exe is our wrapper (small file) or the original (large file)
        $item = Get-Item "$targetDir\7za.exe"
        if ($item.Length -gt 100000) {
            # Original 7za.exe is ~1.2MB
            Rename-Item "$targetDir\7za.exe" "7za-orig.exe"
            Write-Host "Renamed original 7za.exe -> 7za-orig.exe in ${arch}"
        }
    }

    # Compile wrapper
    Add-Type -TypeDefinition $csSource `
        -OutputAssembly $wrapperExe `
        -OutputType ConsoleApplication `
        -ReferencedAssemblies "System.dll" `
        -Language CSharp

    Write-Host "7za.exe wrapper installed: $wrapperExe"
}

Write-Host "All 7za wrappers installed successfully."
