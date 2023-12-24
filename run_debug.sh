#!/bin/bash
SAMPLE_RATE=48000
BUFFER_SIZE=512
(trap 'kill 0' SIGINT;\
   surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1030 --osc-out-port=1040 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1031 --osc-out-port=1041 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1032 --osc-out-port=1042 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1033 --osc-out-port=1043 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1034 --osc-out-port=1044 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1035 --osc-out-port=1045 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1036 --osc-out-port=1046 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1037 --osc-out-port=1047 \
 & surge-xt-cli --audio-interface=[0.10] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1038 --osc-out-port=1048 \
 & python3 app.py)