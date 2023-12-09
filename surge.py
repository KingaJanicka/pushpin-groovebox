import surgepy 
import numpy as np
import simpleaudio as sa
from surgepy import constants as srgco

sample_rate = 44100

s = surgepy.createSurge(sample_rate )

twosecondsInBlocks = int( 10 * s.getSampleRate() / s.getBlockSize() )
buf = s.createMultiBlock( twosecondsInBlocks )

patch = s.getPatch()
pan = patch["scene"][0]["pan"]


# for i in patch["scene"][0]:
#         print(patch["scene"][0][i])

ampeg0 = patch["scene"][0]["adsr"][srgco.adsr_ampeg]

s.setParamVal( ampeg0["a"], -2 )
s.setParamVal( ampeg0["r"], 0.3 )
s.setParamVal( pan , 0.5)

# Play alternating .05 second silence, .4 seconds note, 0.05 second silence
pos = 0
silence = int( 0.4 * s.getSampleRate() / s.getBlockSize() )
hold = int( 1 * s.getSampleRate() / s.getBlockSize() )

for i in range( 4 ):
    
    s.processMultiBlock( buf, pos, silence )
    pos = pos + silence
    
    # Play note on channel 0 at velcity 127 with 0 detune
    s.playNote( 0, 30 + i * 7, 127, 0 )
    s.processMultiBlock( buf, pos, hold )
    pos = pos + hold
    print(s.getParamDisplay(ampeg0["a"]))
    # and release the note
    s.releaseNote( 0, 30 + i * 7, 0 )
    s.processMultiBlock( buf, pos, silence )
    pos = pos + silence

# normalize to 16-bit range
# convert to 16-bit data

buf *= 32767 / np.max(np.abs(buf))
audio = buf.astype(np.int16)
audio = np.swapaxes(audio, 0, 1)
audio = audio.copy(order='C')
print(buf)
print(audio.flags)
# start playback

play_obj = sa.play_buffer(audio, 2, 2, sample_rate)

#TODO: Seems like it's playing one channel after the other

# wait for playback to finish before exiting
play_obj.wait_done()
