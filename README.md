# Audio event detection
The script is modified from [craigfrancis/audio-detect](https://github.com/craigfrancis/audio-detect).\
I removed most of the code, there's just a single line terminal output with the progress.\
It exits when the first match happens and override the timestamp with zeros if no match is found.
## Installation
```sh
install -D -m 755 <(curl -fsSL git.io/JTUWM) ~/.local/bin/getlogotime
```
## Usage
```sh
getlogotime input logo
```
The inputs can be any file with an audio in it that ffmpeg can process.\
The logo can be a file or a folder containing files.
## Examples
`getlogotime input.mp2 introsound.wav`
`getlogotime input.ac3 logofolder`
## bash/zsh implementation
If you want to use `getlogotime`-s output in an ffmpeg command, you can do for example:
```sh
logotime=$(getlogotime input.mp2 logo.wav)
ffmpeg -i input.mp2 -ss ${logotime##*$'\r'} -c copy kek.mp2
```
![image](https://i.kek.sh/fdDz4wuwPbA.gif)
