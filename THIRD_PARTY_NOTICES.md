# Third-party notices

## Groove MIDI Dataset v1.0.0

`backend/app/engine/models/gmd-performance-v1.json` contains aggregated statistical parameters learned
from the Groove MIDI Dataset. The raw MIDI recordings are not redistributed in this repository.

- Provider: Google LLC
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Dataset: https://magenta.withgoogle.com/datasets/groove
- MIDI-only archive SHA-256:
  `651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e`
- Citation: Jon Gillick, Adam Roberts, Jesse Engel, Douglas Eck, and David Bamman, “Learning to Groove
  with Inverse Sequence Transformations,” ICML 2019.

The model was fitted on the prescribed training split's 4/4 beat performances. Validation and test
performances were excluded from fitting; the independent validation metrics are stored in the model
artifact.

## Recorded hi-hat samples

### Closed Hi Hat.wav

- Bundled file: `frontend/public/audio/hihat-closed-378377.mp3`
- Author: karolist
- Source: https://freesound.org/people/karolist/sounds/378377/
- Description: acoustic closed hi-hat recorded in a studio
- License: Creative Commons Zero 1.0 (CC0)
- Bundled form: Freesound's 44.1 kHz high-quality MP3 preview of the CC0 WAV
- SHA-256: `3f58947a704fa4e06666350e9955089c5e20ecb3fc79b2b46b006a2cf1a8eb0a`

### Hi-hat open #1

- Bundled file: `frontend/public/audio/hihat-open-2290.mp3`
- Author: Joseph SARDIN
- Source: https://bigsoundbank.com/hi-hat-open-1-s2290.html
- Recording: SoundDevices MixPre-3, Neumann KM184, mono, 48 kHz/24-bit source
- License: CC0 / public-domain equivalent
- Bundled form: first 1.8 seconds copied from the provider's 320 kbps MP3 without re-encoding
- SHA-256: `0286a5e3eda146b801dfaa739ea5870f2bb878bd8a993d4d6df85f1b6d04ae04`

### Hi-Hat Closed Hit - Clean

- Bundled file: `frontend/public/audio/hihat-closed-674296.mp3`
- Author: TheEndOfACycle
- Source: https://freesound.org/people/TheEndOfACycle/sounds/674296/
- Description: non-produced acoustic closed hi-hat one-shot
- License: Creative Commons Zero 1.0 (CC0)
- Bundled form: Freesound's 44.1 kHz stereo high-quality MP3 preview of the CC0 WAV
- SHA-256: `c29ab7053fd347b22f654aa83f2dc0d293bebea118a5ee7e96d6050e97ada752`

### Hi-hat open #2

- Bundled file: `frontend/public/audio/hihat-open-2291.mp3`
- Author: Joseph SARDIN
- Source: https://bigsoundbank.com/hi-hat-open-2-s2291.html
- Recording: SoundDevices MixPre-3, Neumann KM184, mono, 48 kHz/24-bit source
- License: CC0 / public-domain equivalent
- Bundled form: first 1.8 seconds copied from the provider's 320 kbps MP3 without re-encoding
- SHA-256: `d18207e8cb9327e1079980ea36feca3e0c044055dd7db562ec3a698d6d5eb527`

## Recorded kick and snare samples

The following four one-shots are from dossantosbarbosa's `Drum Kit 1` pack, recorded from an
acoustic Tama Starclassic kit at a studio. Every bundled file is Freesound's 44.1 kHz stereo
high-quality MP3 preview of the corresponding CC0 WAV.

### KickNormal.wav

- Bundled file: `frontend/public/audio/kick-221145.mp3`
- Author: dossantosbarbosa
- Source: https://freesound.org/people/dossantosbarbosa/sounds/221145/
- License: Creative Commons Zero 1.0 (CC0)
- SHA-256: `68a3eed4a151c2e5912c76fc03b68d5645aa3a779898fe2398cf9761711b02bd`

### KickNormal2.wav

- Bundled file: `frontend/public/audio/kick-221144.mp3`
- Author: dossantosbarbosa
- Source: https://freesound.org/people/dossantosbarbosa/sounds/221144/
- License: Creative Commons Zero 1.0 (CC0)
- SHA-256: `a5d73293fafc0fd0a201c7c696569b2f2fa0c0ae944031ada1df0b76d01acd6a`

### SnareNormal2.wav

- Bundled file: `frontend/public/audio/snare-221143.mp3`
- Author: dossantosbarbosa
- Source: https://freesound.org/people/dossantosbarbosa/sounds/221143/
- License: Creative Commons Zero 1.0 (CC0)
- SHA-256: `714e72878242036daf7ad32aeb04041824e9a3ec8b5a6bd49615ea33b3cfc27f`

### SnareNormal3.wav

- Bundled file: `frontend/public/audio/snare-221142.mp3`
- Author: dossantosbarbosa
- Source: https://freesound.org/people/dossantosbarbosa/sounds/221142/
- License: Creative Commons Zero 1.0 (CC0)
- SHA-256: `10e3d3a0393a92cf9bab1c39cf17b20992f359dd1519b139f03dc0bf35804dc1`

## Recorded auxiliary percussion samples

These short wooden Agogô/block strikes were recorded in a studio by Joseph SARDIN as 48 kHz/24-bit
mono sources using a SoundDevices MixPre-3 and Neumann KM184. Both are distributed under CC0 / a
public-domain-equivalent license. The bundled files are the provider's MP3 versions without re-encoding.

### Block #1

- Bundled file: `frontend/public/audio/percussion-block-2268.mp3`
- Source: https://bigsoundbank.com/block-2-s2268.html
- Duration: 0.1472 seconds
- SHA-256: `325711130215031eba48ed94fa0cba2bf1831acc11a7f52c79991912d6da91b6`

### Agogo #4

- Bundled file: `frontend/public/audio/percussion-agogo-2260.mp3`
- Source: https://bigsoundbank.com/agogo-4-s2260.html
- Duration: 0.1712 seconds
- SHA-256: `db8c513895cc4c1c8926acc31db4c54ee9afb2a5960ca8a27575c6e738a622cf`
