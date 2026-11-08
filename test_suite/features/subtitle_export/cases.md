# SRT export

Unit checks write actual SRT through pysubs2, parse timing/IPA/Unicode, preserve literal
braces and protect literal backslash sequences from the library's ASS intermediary.
The English video browser baseline additionally downloads the actual generated SRT.
Timing remains phrase-duration estimation, not forced alignment or word-level karaoke.
