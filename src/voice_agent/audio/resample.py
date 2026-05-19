"""Small PCM16 mono resampler for telephony-rate conversions."""

from array import array


def pcm16_bytes_to_samples(data: bytes) -> array:
    if len(data) % 2 != 0:
        raise ValueError("PCM16 data length must be even.")
    samples = array("h")
    samples.frombytes(data)
    if samples.itemsize != 2:
        raise RuntimeError("This platform does not expose 16-bit signed array samples.")
    return samples


def samples_to_pcm16_bytes(samples: array) -> bytes:
    if samples.typecode != "h":
        raise TypeError("Expected signed 16-bit sample array.")
    return samples.tobytes()


def resample_pcm16_mono(data: bytes, source_rate: int, target_rate: int) -> bytes:
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("Sample rates must be positive.")
    if source_rate == target_rate or not data:
        return data

    input_samples = pcm16_bytes_to_samples(data)
    if len(input_samples) == 1:
        output_len = max(1, round(target_rate / source_rate))
        return samples_to_pcm16_bytes(array("h", [input_samples[0]] * output_len))

    output_len = max(1, round(len(input_samples) * target_rate / source_rate))
    ratio = source_rate / target_rate
    output = array("h")

    for index in range(output_len):
        source_pos = index * ratio
        left_index = int(source_pos)
        right_index = min(left_index + 1, len(input_samples) - 1)
        fraction = source_pos - left_index
        interpolated = input_samples[left_index] + (
            input_samples[right_index] - input_samples[left_index]
        ) * fraction
        output.append(max(-32768, min(32767, round(interpolated))))

    return samples_to_pcm16_bytes(output)
