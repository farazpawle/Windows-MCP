# Throwaway TopMost test window for live windows-mcp tests. Logs every key, click and wheel
# it receives (with the modifiers held at that moment) to -Log. With -TextBox it also holds a
# multiline text box and rewrites "<Log>.text" with its full content on every change.
# Closes itself after -Seconds so a crashed test script never leaves it behind.
# Start it WITHOUT -WindowStyle Hidden: the form inherits SW_HIDE and input then lands behind it.
param(
    [Parameter(Mandatory)] [string]$Title,
    [Parameter(Mandatory)] [string]$Log,
    [int]$X = 300, [int]$Y = 300, [int]$Width = 420, [int]$Height = 280,
    [int]$Seconds = 90,
    [switch]$TextBox,
    [switch]$ScrollBars  # with -TextBox: a vertical scroll bar (a ScrollPattern for UIA)
)
Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @"
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;
public class HarnessForm : Form {
    [DllImport("user32.dll")] static extern short GetKeyState(int vk);
    public string LogPath;
    static bool Down(int vk) { return (GetKeyState(vk) & 0x8000) != 0; }
    static string Held() {
        string s = "";
        if (Down(0x11)) s += "ctrl ";
        if (Down(0x10)) s += "shift ";
        if (Down(0x12)) s += "alt ";
        if (Down(0x5B) || Down(0x5C)) s += "win ";
        return s.Trim();
    }
    public void Write(string line) {
        for (int i = 0; i < 20; i++) {
            try { File.AppendAllText(LogPath, line + " held=[" + Held() + "]" + Environment.NewLine); return; }
            catch (IOException) { System.Threading.Thread.Sleep(10); }  // reader has it open
        }
    }
    public HarnessForm() {
        KeyPreview = true;  // keys reach the form even when the text box has focus
        KeyDown += (s, e) => Write("key " + e.KeyCode);
    }
    protected override void WndProc(ref Message m) {
        switch (m.Msg) {
            case 0x0201: Write("lbutton"); break;  // WM_LBUTTONDOWN
            case 0x0203: Write("ldouble"); break;  // WM_LBUTTONDBLCLK
            case 0x0204: Write("rbutton"); break;  // WM_RBUTTONDOWN
            case 0x0207: Write("mbutton"); break;  // WM_MBUTTONDOWN
            case 0x020A: Write("wheel " + ((short)((long)m.WParam >> 16))); break;
            case 0x020E: Write("hwheel " + ((short)((long)m.WParam >> 16))); break;
        }
        base.WndProc(ref m);
    }
}
"@
$form = New-Object HarnessForm
$form.LogPath = $Log
$form.Text = $Title
$form.StartPosition = "Manual"
$form.Location = New-Object Drawing.Point($X, $Y)
$form.Size = New-Object Drawing.Size($Width, $Height)
$form.TopMost = $true
if ($TextBox) {
    $box = New-Object Windows.Forms.TextBox
    $box.Multiline = $true
    $box.Dock = "Fill"
    if ($ScrollBars) { $box.ScrollBars = "Vertical" }
    $textPath = "$Log.text"
    $box.Add_TextChanged({ try { [IO.File]::WriteAllText($textPath, $box.Text) } catch {} })
    # Clicks and wheel on the box never reach the form's WndProc, so log them here.
    # (Horizontal wheel has no TextBox event: test it without -TextBox.)
    $box.Add_MouseDown({
        param($s, $e)
        $name = @{ Left = "lbutton"; Right = "rbutton"; Middle = "mbutton" }[$e.Button.ToString()]
        if ($name) { $form.Write($name) }
    })
    $box.Add_MouseWheel({ param($s, $e) $form.Write("wheel " + $e.Delta) })
    $form.Controls.Add($box)
}
$timer = New-Object Windows.Forms.Timer
$timer.Interval = $Seconds * 1000
$timer.Add_Tick({ $form.Close() })
$timer.Start()
[void]$form.ShowDialog()
