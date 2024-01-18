#!/bin/bash
SAMPLE_RATE=96000
# SAMPLE_RATE=48000
BUFFER_SIZE=512
(trap 'kill 0' SIGINT;\
   surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1030 --osc-out-port=1040 1>/var/log/surge-xt-cli/0.log 2>/var/log/surge-xt-cli/0-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1031 --osc-out-port=1041 1>/var/log/surge-xt-cli/1.log 2>/var/log/surge-xt-cli/1-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1032 --osc-out-port=1042 1>/var/log/surge-xt-cli/2.log 2>/var/log/surge-xt-cli/2-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1033 --osc-out-port=1043 1>/var/log/surge-xt-cli/3.log 2>/var/log/surge-xt-cli/3-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1034 --osc-out-port=1044 1>/var/log/surge-xt-cli/4.log 2>/var/log/surge-xt-cli/4-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1035 --osc-out-port=1045 1>/var/log/surge-xt-cli/5.log 2>/var/log/surge-xt-cli/5-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1036 --osc-out-port=1046 1>/var/log/surge-xt-cli/6.log 2>/var/log/surge-xt-cli/6-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1037 --osc-out-port=1047 1>/var/log/surge-xt-cli/7.log 2>/var/log/surge-xt-cli/7-err.log\
 & surge-xt-cli --audio-interface=[0.0] --sample-rate=$SAMPLE_RATE --buffer-size=$BUFFER_SIZE --osc-in-port=1038 --osc-out-port=1048 1>/var/log/surge-xt-cli/8.log 2>/var/log/surge-xt-cli/8-err.log\
 & python3 app.py)