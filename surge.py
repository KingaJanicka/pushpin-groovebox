import surgepy 
import numpy as np
import time

import simpleaudio as sa

sample_rate = 44100

s = surgepy.createSurge(sample_rate )

twosecondsInBlocks = int( 2 * s.getSampleRate() / s.getBlockSize() )
buf = s.createMultiBlock( twosecondsInBlocks )

# Play alternating .05 second silence, .4 seconds note, 0.05 second silence
pos = 0
silence = int( 0.05 * s.getSampleRate() / s.getBlockSize() )
hold = int( 0.4 * s.getSampleRate() / s.getBlockSize() )
print(s.getSampleRate())

for i in range( 4 ):
    
    s.processMultiBlock(buf, pos, silence )
    pos = pos + silence
    
    # Play note on channel 0 at velcity 127 with 0 detune
    s.playNote( 0, 60 + i * 7, 127, 0 )
    s.processMultiBlock( buf, pos, hold )
    pos = pos + hold
    
    # and release the note
    s.releaseNote( 0, 60 + i * 7, 0 )
    s.processMultiBlock(buf, pos, silence )
    pos = pos + silence



# normalize to 16-bit range
# convert to 16-bit data
buf *= 32767 / np.max(np.abs(buf))
audio = buf.astype(np.int16)
# start playback
play_obj = sa.play_buffer(audio[0], 1, 2, sample_rate)

# wait for playback to finish before exiting
play_obj.wait_done()
