import * as Tone from 'tone'

/** Starts Web Audio from the button gesture and reports blocked output clearly. */
export async function prepareAudioOutput() {
  await Tone.start()
  Tone.getDestination().mute = false
  if (Tone.getContext().state !== 'running') {
    throw new Error('このブラウザでは音声出力が許可されていません。端末の消音を解除してから、ページを再読み込みしてもう一度再生してください。')
  }
}
