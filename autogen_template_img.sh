#!/bin/bash
for d in templates/*; do
	caps=""
	for c in "$d"/caption*.txt; do caps+="/$(tr ' ' '_' <"$c")"; done
	curl -s "https://api.memegen.link/images/$(cat "$d/meme_name.txt")$caps.png" -o "$d/img.png"
done
