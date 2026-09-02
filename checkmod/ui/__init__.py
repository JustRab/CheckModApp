"""Widget toolkit for CheckMod.

Tkinter's stock widgets cannot be styled far enough to look modern (flat
fills, rounded corners, hover states, animated toggles), and ``ttk`` themes
behave differently on every platform. So every interactive element here is
drawn by hand on a :class:`tkinter.Canvas`.

That gives three things this project needs:

* pixel-identical rendering on Windows, macOS and Linux;
* full runtime re-skinning - each widget exposes ``restyle(theme, fonts)``
  and repaints itself, which is how Dev Mode changes themes live;
* no third-party dependency, keeping the portable executable small.
"""
