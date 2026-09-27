# Newsreader for social cards

`newsreader-variable.ttf` is the Newsreader variable font from [Google Fonts](https://github.com/google/fonts/blob/main/ofl/newsreader/Newsreader%5Bopsz%2Cwght%5D.ttf), licensed under the adjacent `OFL.txt`.

The build-time social-card renderer uses this local TTF through Sharp/Pango rather than relying on installed system fonts or fetching fonts during the build. The website continues to use its existing WOFF2 font in `public/fonts/newsreader/`.
