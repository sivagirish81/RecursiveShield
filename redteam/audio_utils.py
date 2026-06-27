import wave
import os

def splice_audio(host_path: str, splice_path: str, output_path: str, timestamp_sec: float, replace: bool = True):
    """
    Splices the WAV audio from splice_path into the WAV audio from host_path
    at the specified timestamp_sec.
    
    If replace is True, the splice audio overwrites the host audio starting at timestamp_sec.
    If replace is False, the splice audio is inserted, shifting the remaining host audio.
    """
    if not os.path.exists(host_path):
        raise FileNotFoundError(f"Host audio file not found: {host_path}")
    if not os.path.exists(splice_path):
        raise FileNotFoundError(f"Splice audio file not found: {splice_path}")

    with wave.open(host_path, 'rb') as host:
        host_params = host.getparams()
        nchannels = host_params.nchannels
        sampwidth = host_params.sampwidth
        framerate = host_params.framerate
        nframes = host.getnframes()
        host_data = host.readframes(nframes)

    with wave.open(splice_path, 'rb') as splice:
        splice_params = splice.getparams()
        if splice_params.nchannels != nchannels or splice_params.sampwidth != sampwidth or splice_params.framerate != framerate:
            # Format mismatch. In a production environment we'd resample.
            # We will raise a ValueError or print a warning and attempt to write anyway.
            print(f"Warning: format mismatch! Host: {host_params}, Splice: {splice_params}")
        
        splice_frames = splice.getnframes()
        splice_data = splice.readframes(splice_frames)

    frame_size = nchannels * sampwidth
    insert_frame = int(timestamp_sec * framerate)
    insert_byte = insert_frame * frame_size

    # Ensure insert_byte is within range of host data length
    insert_byte = min(insert_byte, len(host_data))

    if replace:
        # Replace host data from insert_byte onwards up to len(splice_data)
        new_data = host_data[:insert_byte] + splice_data + host_data[insert_byte + len(splice_data):]
    else:
        # Insert splice data, shifting host data
        new_data = host_data[:insert_byte] + splice_data + host_data[insert_byte:]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with wave.open(output_path, 'wb') as out:
        out.setparams(host_params)
        out.writeframes(new_data)
    
    print(f"Successfully spliced audio. Output written to {output_path}")
