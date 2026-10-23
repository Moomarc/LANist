using System;
using System.Diagnostics;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string extra = JoinArgs(args);

        Process process = TryLaunch("pyw.exe", "-3 -m lanist" + extra, baseDir);
        if (process == null)
        {
            process = TryLaunch("pythonw.exe", "-m lanist" + extra, baseDir);
        }
        if (process == null)
        {
            process = TryLaunch("py.exe", "-3 -m lanist" + extra, baseDir);
        }
        if (process == null)
        {
            process = TryLaunch("python.exe", "-m lanist" + extra, baseDir);
        }

        if (process == null)
        {
            MessageBox.Show(
                "没有找到 Python。\n\n请先安装 Python 3.9 或更新版本，安装时保留 py launcher 与 tcl/tk，然后重新打开 LANist.exe。",
                "LANist",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        try
        {
            if (process.WaitForExit(1500) && process.ExitCode != 0)
            {
                MessageBox.Show(
                    "LANist 启动失败（退出码 " + process.ExitCode + "）。\n\n"
                    + "请确认 LANist.exe 与 lanist 文件夹放在一起，并在命令行运行：\n"
                    + "py -3 -m lanist\n\n查看具体错误。",
                    "LANist",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
            }
        }
        catch (InvalidOperationException)
        {
        }
    }

    private static Process TryLaunch(string file, string arguments, string workingDirectory)
    {
        try
        {
            ProcessStartInfo info = new ProcessStartInfo(file, arguments);
            info.WorkingDirectory = workingDirectory;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            return Process.Start(info);
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static string JoinArgs(string[] args)
    {
        if (args == null || args.Length == 0)
        {
            return "";
        }
        string[] parts = new string[args.Length];
        for (int i = 0; i < args.Length; i++)
        {
            parts[i] = "\"" + args[i].Replace("\"", "\\\"") + "\"";
        }
        return " " + string.Join(" ", parts);
    }
}
