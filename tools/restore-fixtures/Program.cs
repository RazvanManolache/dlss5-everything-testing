using System.Reflection;
using System.Text.Json;

if (args.Length != 2) throw new ArgumentException("Expected installer assembly and suite directory.");
var assembly = Assembly.LoadFrom(Path.GetFullPath(args[0]));
var engineType = assembly.GetType("Dlss5CompatApp.InstallerEngine", throwOnError: true)!;
var engine = Activator.CreateInstance(engineType, [(Action<string>)Console.WriteLine, null])!;
var restore = engineType.GetMethod("RestoreAsync")!;
var suite = Path.GetFullPath(args[1]);
var gamesRoot = Path.GetFullPath(Path.Combine(suite, "games")) + Path.DirectorySeparatorChar;
using var matrix = JsonDocument.Parse(File.ReadAllText(Path.Combine(suite, "matrix.json")));
var failures = new List<string>();
foreach (var game in matrix.RootElement.GetProperty("games").EnumerateArray())
{
    var id = game.GetProperty("id").GetString()!;
    var folder = Path.GetFullPath(Path.Combine(suite, game.GetProperty("install_directory").GetString()!));
    if (!folder.StartsWith(gamesRoot, StringComparison.OrdinalIgnoreCase) ||
        File.GetAttributes(folder).HasFlag(FileAttributes.ReparsePoint))
        throw new IOException("Unsafe fixture directory.");
    try
    {
        await (Task)restore.Invoke(engine, [folder, CancellationToken.None])!;
        Console.WriteLine(JsonSerializer.Serialize(new { id, restored = true }));
    }
    catch (Exception error)
    {
        failures.Add(id);
        Console.Error.WriteLine(JsonSerializer.Serialize(new { id, restored = false,
            error = (error.InnerException ?? error).Message }));
    }
}
return failures.Count == 0 ? 0 : 1;
