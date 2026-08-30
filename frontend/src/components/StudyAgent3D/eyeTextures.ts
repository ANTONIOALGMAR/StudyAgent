import * as THREE from 'three'

function makeCanvas(size: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement('canvas')
  c.width = size
  c.height = size
  const ctx = c.getContext('2d')!
  return [c, ctx]
}

function toTexture(canvas: HTMLCanvasElement): THREE.Texture {
  const t = new THREE.CanvasTexture(canvas)
  t.colorSpace = THREE.SRGBColorSpace
  t.wrapS = THREE.ClampToEdgeWrapping
  t.wrapT = THREE.ClampToEdgeWrapping
  t.anisotropy = 8
  t.needsUpdate = true
  return t
}

export function createIrisTexture(color = 'azul'): THREE.Texture {
  const size = 1024
  const [canvas, ctx] = makeCanvas(size)
  const c = size / 2
  const R = size / 2 - 6

  // apertura (pupila) relativa
  const pupilR = R * 0.34
  const limboR = R - R * 0.06
  const irisOuter = R * 0.94

  const hue =
    color === 'azul'
      ? { base: '#7dd9ff', mid: '#38c3ff', dark: '#0095d9', ring: '#00cfff' }
      : color === 'verde'
        ? { base: '#5c8a4a', mid: '#4c743c', dark: '#335028', ring: '#263d1e' }
        : { base: '#6b4a2a', mid: '#54371d', dark: '#3a2410', ring: '#2a1a0a' }

  // corpo da íris (gradiente radial)
  const g = ctx.createRadialGradient(c, c, pupilR, c, c, irisOuter)
  g.addColorStop(0, hue.dark)
  g.addColorStop(0.35, hue.mid)
  g.addColorStop(0.75, hue.base)
  g.addColorStop(1, hue.base)
  ctx.fillStyle = g
  ctx.beginPath()
  ctx.arc(c, c, irisOuter, 0, Math.PI * 2)
  ctx.fill()

  // raios radiais (crypts / fibras) com leve padrão espiralado
  ctx.save()
  ctx.globalCompositeOperation = 'overlay'
  ctx.translate(c, c)
  const spokes = 320
  const rotOff = 0.55
  for (let i = 0; i < spokes; i++) {
    const a = (i / spokes) * Math.PI * 2
    ctx.save()
    ctx.rotate(a + rotOff)
    ctx.strokeStyle = i % 2 === 0 ? 'rgba(0,0,0,0.28)' : 'rgba(255,255,255,0.12)'
    ctx.lineWidth = 1.2 + Math.random() * 1.6
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(pupilR * 0.6, 0)
    ctx.lineTo(irisOuter * (0.92 + Math.random() * 0.08), 0)
    ctx.stroke()
    ctx.restore()
  }
  ctx.restore()

  // traço sutil no limbo externo
  ctx.strokeStyle = hue.ring
  ctx.lineWidth = 8
  ctx.beginPath()
  ctx.arc(c, c, limboR, 0, Math.PI * 2)
  ctx.stroke()

  // anel interno tecnológico (junto à pupila, luminoso)
  const ringR = pupilR * 1.45
  ctx.save()
  ctx.strokeStyle = `rgba(0,207,255,0.8)`
  ctx.lineWidth = 5
  ctx.shadowColor = '#00cfff'
  ctx.shadowBlur = 22
  ctx.beginPath()
  ctx.arc(c, c, ringR, 0, Math.PI * 2)
  ctx.stroke()
  ctx.restore()

  // leve emissão ciano no corpo da íris (efeito luminoso holográfico)
  ctx.save()
  ctx.globalCompositeOperation = 'lighter'
  const glow = ctx.createRadialGradient(c, c, pupilR, c, c, irisOuter * 0.9)
  glow.addColorStop(0, 'rgba(120,225,255,0.28)')
  glow.addColorStop(0.5, 'rgba(60,200,255,0.10)')
  glow.addColorStop(1, 'rgba(0,207,255,0)')
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(c, c, irisOuter, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()

  // pupila preta
  const pg = ctx.createRadialGradient(c, c, pupilR * 0.2, c, c, pupilR)
  pg.addColorStop(0, '#000000')
  pg.addColorStop(1, '#0a0a0a')
  ctx.fillStyle = pg
  ctx.beginPath()
  ctx.arc(c, c, pupilR, 0, Math.PI * 2)
  ctx.fill()

  // realce especular (reflexo) deslocado para cima-esquerda
  const hsR = R * 0.16
  const hx = c - R * 0.34
  const hy = c - R * 0.4
  const hg = ctx.createRadialGradient(hx, hy, 0, hx, hy, hsR)
  hg.addColorStop(0, 'rgba(255,255,255,0.9)')
  hg.addColorStop(0.4, 'rgba(255,255,255,0.35)')
  hg.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = hg
  ctx.beginPath()
  ctx.arc(hx, hy, hsR, 0, Math.PI * 2)
  ctx.fill()

  return toTexture(canvas)
}

export function createScleraTexture(): THREE.Texture {
  const size = 1024
  const [canvas, ctx] = makeCanvas(size)
  const c = size / 2
  const R = size / 2 - 6

  // base branca levemente fria
  const g = ctx.createRadialGradient(c, c, R * 0.2, c, c, R)
  g.addColorStop(0, '#ffffff')
  g.addColorStop(0.7, '#fbfbfd')
  g.addColorStop(1, '#eef0f4')
  ctx.fillStyle = g
  ctx.beginPath()
  ctx.arc(c, c, R, 0, Math.PI * 2)
  ctx.fill()

  // veias sanguíneas finas e sutis em direção ao canto
  ctx.save()
  ctx.translate(c, c)
  for (let i = 0; i < 42; i++) {
    const a = -Math.PI * (0.62 + Math.random() * 0.26)
    const startR = R * (0.42 + Math.random() * 0.3)
    const len = R * (0.14 + Math.random() * 0.3)
    ctx.strokeStyle = `rgba(200,60,60,${0.10 + Math.random() * 0.12})`
    ctx.lineWidth = 0.8 + Math.random() * 1.2
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(Math.cos(a) * startR, Math.sin(a) * startR)
    let x = Math.cos(a) * startR
    let y = Math.sin(a) * startR
    for (let s = 1; s <= 4; s++) {
      const rr = startR + (len * s) / 4
      x += (Math.cos(a) + (Math.random() - 0.5) * 0.4) * (len / 4)
      y += (Math.sin(a) + (Math.random() - 0.5) * 0.4) * (len / 4)
      ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr)
    }
    ctx.stroke()
  }
  ctx.restore()

  return toTexture(canvas)
}
