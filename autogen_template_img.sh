#!/bin/bash
for d in templates/*; do
	f=$(basename "$d")
	c1=$(cat "$d/caption1.txt" 2>/dev/null)
	c2=$(cat "$d/caption2.txt" 2>/dev/null)
	c1=${c1:-_}
	c2=${c2:-_}
	curl -s "https://api.memegen.link/images/$f/${c1// /_}/${c2// /_}.png" -o "$d/img.png"
done
