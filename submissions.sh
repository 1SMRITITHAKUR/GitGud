#!/bin/bash
curl -s https://api.github.com/repos/kartinul/GitGud/contents/submissions | jq -r '.[].name' | while read -r n; do
	m=$(curl -s https://raw.githubusercontent.com/kartinul/GitGud/main/submissions/$n/meme_name.txt | tr -d '\r\n')
	c1=$(curl -s https://raw.githubusercontent.com/kartinul/GitGud/main/submissions/$n/caption1.txt | tr -d '\r\n' | tr ' ' '_')
	c2=$(curl -s https://raw.githubusercontent.com/kartinul/GitGud/main/submissions/$n/caption2.txt | tr -d '\r\n' | tr ' ' '_')
	curl -s "https://api.memegen.link/images/$m/$c1/$c2.png" -o "output/$n.png"
done
