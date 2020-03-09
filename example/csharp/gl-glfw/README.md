Example: gl-glfw
================

This is basic example showcasing `glad` in combination with
[glfw-net](https://www.nuget.org/packages/glfw-net).

Make sure you have the
[.NET Core 3.1 SDK](https://dotnet.microsoft.com/download) installed
and then run the example use the following command:

```sh
./init.sh && dotnet run
```

The `init.sh` script is just a small utility used to generate
the `GL.cs` class into the `build/` directory.

This example is a basic example of the
[glfw-net package](https://www.nuget.org/packages/glfw-net) with some
OpenGL instructions added and just one additional line
to initialize `glad`:

```c#
GL.Load(Glfw.GetProcAddress);
```

That's all that is needed to initialize and use OpenGL using `glad`!
