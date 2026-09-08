using System.Threading;

// Structural AUMID launch probe only; this does not claim functional app coverage.
// Windows supplies the activation environment, unlike the separate isolation probe.
public static class Program
{
    [System.STAThread]
    public static int Main()
    {
        Thread.Sleep(10000); // Longer than the three-second MSIX liveness window.
        return 0;
    }
}
