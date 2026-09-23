# Adds or removes a temporary 800x600 virtual second screen for multi-monitor live tests.
# Uses the signed "Driver.Only" package of VirtualDrivers/Virtual-Display-Driver
# (hardware id Root\MttVDD). Must run elevated: pnputil cannot create a root device,
# so the device node is made through SetupAPI and the driver bound with newdev.
#
#   powershell -File virtual_display.ps1 -Install -Source <unzipped VirtualDisplayDriver folder>
#   powershell -File virtual_display.ps1 -Remove
# -Log <file> appends a transcript (an elevated window's output is otherwise lost).
param(
    [switch]$Install,
    [switch]$Remove,
    [string]$Source,
    [string]$Log
)
$ErrorActionPreference = 'Stop'
$HwId = 'Root\MttVDD'
$Home_ = 'C:\VirtualDisplayDriver'  # the driver reads vdd_settings.xml from here
if ($Log) { Start-Transcript -Append -Path $Log | Out-Null }

function Get-VddDevices {
    Get-CimInstance Win32_PnPEntity -Filter "PNPClass = 'Display'" |
        Where-Object { $_.HardwareID -contains $HwId }
}

try {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw 'Run this elevated (admin).' }

    if ($Install) {
        if (-not $Source -or -not (Test-Path "$Source\MttVDD.inf")) { throw "-Source must hold MttVDD.inf" }
        New-Item -ItemType Directory -Force $Home_ | Out-Null
        Copy-Item "$Source\*" $Home_ -Force
        # Keep only 800x600 so the screen stays small (the package also offers up to 4K).
        $settings = [xml](Get-Content -Raw "$Home_\vdd_settings.xml")
        foreach ($r in @($settings.SelectNodes('//resolutions/resolution'))) {
            if ($r.width -ne '800' -or $r.height -ne '600') { [void]$r.ParentNode.RemoveChild($r) }
        }
        $settings.Save("$Home_\vdd_settings.xml")

        if (Get-VddDevices) {
            Write-Output 'Virtual screen device already present; nothing created.'
        } else {
            Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class VddSetup {
    [StructLayout(LayoutKind.Sequential)]
    public struct SP_DEVINFO_DATA { public int cbSize; public Guid ClassGuid; public int DevInst; public IntPtr Reserved; }
    [DllImport("setupapi.dll", SetLastError = true)]
    static extern IntPtr SetupDiCreateDeviceInfoList(ref Guid g, IntPtr hwnd);
    [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool SetupDiCreateDeviceInfoW(IntPtr set, string name, ref Guid g, string desc, IntPtr hwnd, int flags, ref SP_DEVINFO_DATA d);
    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiSetDeviceRegistryPropertyW(IntPtr set, ref SP_DEVINFO_DATA d, int prop, byte[] buf, int size);
    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiCallClassInstaller(int fn, IntPtr set, ref SP_DEVINFO_DATA d);
    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);
    [DllImport("newdev.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool UpdateDriverForPlugAndPlayDevicesW(IntPtr hwnd, string hwid, string inf, int flags, out bool reboot);

    public static void Install(string hwid, string inf) {
        Guid display = new Guid("4d36e968-e325-11ce-bfc1-08002be10318");
        IntPtr set = SetupDiCreateDeviceInfoList(ref display, IntPtr.Zero);
        if (set == new IntPtr(-1)) throw new Win32Exception();
        try {
            SP_DEVINFO_DATA d = new SP_DEVINFO_DATA();
            d.cbSize = Marshal.SizeOf(d);
            if (!SetupDiCreateDeviceInfoW(set, "Display", ref display, null, IntPtr.Zero, 1, ref d))  // DICD_GENERATE_ID
                throw new Win32Exception();
            byte[] ids = Encoding.Unicode.GetBytes(hwid + "\0\0");
            if (!SetupDiSetDeviceRegistryPropertyW(set, ref d, 1, ids, ids.Length))  // SPDRP_HARDWAREID
                throw new Win32Exception();
            if (!SetupDiCallClassInstaller(0x19, set, ref d))  // DIF_REGISTERDEVICE
                throw new Win32Exception();
        } finally {
            SetupDiDestroyDeviceInfoList(set);
        }
        bool reboot;
        if (!UpdateDriverForPlugAndPlayDevicesW(IntPtr.Zero, hwid, inf, 1, out reboot))  // INSTALLFLAG_FORCE
            throw new Win32Exception();
    }
}
'@
            [VddSetup]::Install($HwId, "$Home_\MttVDD.inf")
            Write-Output 'Virtual screen installed.'
        }
    }

    if ($Remove) {
        foreach ($dev in @(Get-VddDevices)) {
            $inf = (Get-CimInstance Win32_PnPSignedDriver -Filter "DeviceID = '$($dev.PNPDeviceID -replace '\\', '\\')'").InfName
            pnputil /remove-device "$($dev.PNPDeviceID)" | Write-Output
            if ($inf -like 'oem*.inf') { pnputil /delete-driver $inf /uninstall | Write-Output }
        }
        if (Test-Path $Home_) { Remove-Item -Recurse -Force $Home_ }
        Write-Output 'Virtual screen removed.'
    }
} catch {
    Write-Output "FAILED: $($_.Exception.Message)"
    exit 1
} finally {
    if ($Log) { Stop-Transcript | Out-Null }
}
