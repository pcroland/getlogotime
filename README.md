# Audio event detection
The script is modified from [craigfrancis/audio-detect](https://github.com/craigfrancis/audio-detect).\
I removed most of the code, there's just a single line terminal output with the progress.\
It exits when the first match happens and override the timestamp with zeros if no match is found.\
\
![image](https://i.kek.sh/fdDz4wuwPbA.gif)
## Installation
```bash
git clone https://github.com/pcroland/getlogotime
cd getlogotime
pip install -r requirements.txt
cp getlogotime.py ~/.local/bin/getlogotime
chmod +x ~/local/bin/getlogotime
hash -r
```
## Usage
```sh
getlogotime input logo
```
The inputs can be any audio (or video with audio inside) file ffmpeg can process.\
For the logo you can specify a single file or a folder containing the intro/logo files.
## Examples
`getlogotime input.mp2 introsound.wav`\
`getlogotime input.ac3 logofolder`
## bash/zsh implementation
If you want to use `getlogotime`-s output in an ffmpeg command, you can do for example:
```bash
logotime=$(getlogotime input.mp2 logo.wav)
ffmpeg -i input.mp2 -ss ${logotime##*$'\r'} -c copy kek.mp2
```
