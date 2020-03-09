using System;
using GLFW;
using OpenGL;

class Program
{
    private static Window window;

    static void Main(string[] args)
    {
        Glfw.WindowHint(Hint.ClientApi, ClientApi.OpenGL);
        Glfw.WindowHint(Hint.ContextVersionMajor, 3);
        Glfw.WindowHint(Hint.ContextVersionMinor, 3);
        Glfw.WindowHint(Hint.OpenglForwardCompatible, true);
        Glfw.WindowHint(Hint.OpenglProfile, Profile.Core);
        Glfw.WindowHint(Hint.Doublebuffer, true);
        Glfw.WindowHint(Hint.Decorated, true);

        window = Glfw.CreateWindow(300, 300, "[glad] C# - OpenGL with GLFW", Monitor.None, Window.None);
        Glfw.MakeContextCurrent(window);

        Glfw.SetKeyCallback(window, KeyCallback);

        GL.Load(Glfw.GetProcAddress);

        while (!Glfw.WindowShouldClose(window))
        {
            Glfw.PollEvents();

            GL.ClearColor(0.7f, 0.9f, 0.1f, 1.0f);
            GL.Clear(GLEnum.GL_COLOR_BUFFER_BIT);

            Glfw.SwapBuffers(window);
        }
    }

    private static void KeyCallback(IntPtr handle, Keys key, int scancode, InputState state, ModifierKeys mods)
    {
        switch (key)
        {
            case Keys.Escape:
                Glfw.SetWindowShouldClose(window, true);
                break;
        }
    }
}
