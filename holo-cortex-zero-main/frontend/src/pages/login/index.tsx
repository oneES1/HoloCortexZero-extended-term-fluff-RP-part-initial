import { useState, useEffect, useRef } from 'react'
import { Box } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useNotification } from '../../hooks/useNotification'
import { adminAuthApi } from '../../services/api/auth'
import { useAuthStore } from '../../stores/auth'
import { useColorMode } from '../../stores/theme'
import logoDarkUrl from '../../assets/logo_darkmode.png'
import logoLightUrl from '../../assets/logo_lightmode.png'

const ACCENT = '#5c9dff'
const SIGNAL = '#57d7c8'
const WARM = '#b98b52'
const REDUCED = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
const NEURAL_PALETTE = {
  deepInk: '#030202',
  midnight: '#08060b',
  oilTeal: '#07110f',
  mutedIndigo: '118, 124, 178',
  softViolet: '142, 104, 132',
  deepTeal: '61, 111, 93',
  agedGold: '185, 139, 82',
  emberRose: '154, 82, 74',
  nodeCore: '170, 178, 184',
} as const

const LIGHT_NEURAL_PALETTE = {
  center: '#ffffff',
  wash: '#f4f7fb',
  edge: '#e7edf5',
  mutedIndigo: '92, 132, 190',
  softViolet: '142, 104, 132',
  deepTeal: '55, 128, 112',
  agedGold: '185, 139, 82',
  emberRose: '154, 82, 74',
  nodeCore: '71, 85, 105',
} as const

function CortexFieldBackground({ mode }: { mode: 'light' | 'dark' }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const seed = (value: number) => Math.sin(value * 928.371) * 0.5 + 0.5
    const nodeCount = 86
    const nodes = Array.from({ length: nodeCount }, (_, index) => {
      const cluster = index % 5
      const radial = seed(index + 1) ** 0.72
      const angle = seed(index + 8.3) * Math.PI * 2
      const clusterX = [0.22, 0.38, 0.56, 0.74, 0.48][cluster]
      const clusterY = [0.36, 0.68, 0.29, 0.58, 0.48][cluster]
      return {
        x: clusterX + Math.cos(angle) * radial * (0.13 + seed(index + 2) * 0.12),
        y: clusterY + Math.sin(angle) * radial * (0.16 + seed(index + 3) * 0.13),
        phase: seed(index + 4) * Math.PI * 2,
        speed: 0.000035 + seed(index + 5) * 0.000085,
        drift: 3 + seed(index + 6) * 8,
        size: 0.45 + seed(index + 7) * 0.95,
        depth: 0.25 + seed(index + 9) * 0.75,
        cluster,
      }
    })

    const synapses = nodes.flatMap((node, index) => {
      const links: Array<{ from: number; to: number; strength: number; phase: number }> = []
      for (let offset = 1; offset <= 5; offset++) {
        const to = (index + Math.floor(seed(index * 10 + offset) * 31) + offset * 7) % nodeCount
        const target = nodes[to]
        const sameCluster = node.cluster === target.cluster
        links.push({
          from: index,
          to,
          strength: sameCluster ? 0.9 : 0.52,
          phase: seed(index + offset * 13) * Math.PI * 2,
        })
      }
      return links
    })

    let width = 0
    let height = 0
    let raf = 0

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const resolveNode = (node: typeof nodes[number], time: number) => {
      const motion = REDUCED ? 0 : time
      const undertow = Math.sin(motion * 0.00009 + node.y * 8.2) * width * 0.012
      const x =
        node.x * width +
        Math.sin(motion * node.speed + node.phase) * node.drift +
        undertow * node.depth
      const y =
        node.y * height +
        Math.cos(motion * (node.speed * 0.82) + node.phase * 1.31) * node.drift * 0.72
      return { x, y }
    }

    const draw = (time = 0) => {
      ctx.clearRect(0, 0, width, height)

      const base = ctx.createRadialGradient(width * 0.46, height * 0.48, 0, width * 0.46, height * 0.48, Math.max(width, height) * 0.82)
      if (mode === 'light') {
        base.addColorStop(0, LIGHT_NEURAL_PALETTE.center)
        base.addColorStop(0.42, LIGHT_NEURAL_PALETTE.wash)
        base.addColorStop(0.76, '#eef3f9')
        base.addColorStop(1, LIGHT_NEURAL_PALETTE.edge)
      } else {
        base.addColorStop(0, NEURAL_PALETTE.oilTeal)
        base.addColorStop(0.34, NEURAL_PALETTE.midnight)
        base.addColorStop(0.72, '#010407')
        base.addColorStop(1, NEURAL_PALETTE.deepInk)
      }
      ctx.fillStyle = base
      ctx.fillRect(0, 0, width, height)

      const colorWash = ctx.createLinearGradient(0, 0, width, height)
      colorWash.addColorStop(0, mode === 'light' ? 'rgba(92, 132, 190, 0.10)' : 'rgba(67, 98, 91, 0.07)')
      colorWash.addColorStop(0.42, mode === 'light' ? 'rgba(142, 104, 132, 0.06)' : 'rgba(92, 58, 78, 0.06)')
      colorWash.addColorStop(1, mode === 'light' ? 'rgba(185, 139, 82, 0.07)' : 'rgba(138, 82, 40, 0.055)')
      ctx.fillStyle = colorWash
      ctx.fillRect(0, 0, width, height)

      const emberWash = ctx.createRadialGradient(width * 0.72, height * 0.72, 0, width * 0.72, height * 0.72, Math.max(width, height) * 0.56)
      emberWash.addColorStop(0, mode === 'light' ? 'rgba(185, 139, 82, 0.10)' : 'rgba(151, 88, 48, 0.085)')
      emberWash.addColorStop(0.48, mode === 'light' ? 'rgba(154, 82, 74, 0.04)' : 'rgba(91, 45, 48, 0.035)')
      emberWash.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = emberWash
      ctx.fillRect(0, 0, width, height)

      ctx.save()
      ctx.globalCompositeOperation = 'source-over'

      const current = nodes.map(node => resolveNode(node, time))

      for (let layer = 0; layer < 4; layer++) {
        const layerAlpha = 0.009 + layer * 0.005
        const wave = REDUCED ? 0 : Math.sin(time * 0.00008 + layer) * 12
        ctx.beginPath()
        for (let step = 0; step <= 96; step++) {
          const t = step / 96
          const x = width * (-0.08 + t * 1.18)
          const y =
            height * (0.23 + layer * 0.18) +
            Math.sin(t * 7.4 + layer * 1.8 + time * 0.00012) * (28 + layer * 16) +
            wave * Math.sin(t * Math.PI)
          if (step === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        const washTone = layer % 2 === 0
          ? (mode === 'light' ? LIGHT_NEURAL_PALETTE.deepTeal : NEURAL_PALETTE.deepTeal)
          : (mode === 'light' ? LIGHT_NEURAL_PALETTE.softViolet : NEURAL_PALETTE.softViolet)
        ctx.strokeStyle = `rgba(${washTone}, ${mode === 'light' ? layerAlpha * 1.6 : layerAlpha})`
        ctx.lineWidth = 16 + layer * 8
        ctx.stroke()
      }

      for (const link of synapses) {
        const from = current[link.from]
        const to = current[link.to]
        const dx = to.x - from.x
        const dy = to.y - from.y
        const distance = Math.hypot(dx, dy)
        const maxDistance = Math.min(width, height) * 0.34
        if (distance > maxDistance) continue
        const pulse = REDUCED ? 0.45 : Math.sin(time * 0.00018 + link.phase) * 0.5 + 0.5
        const alpha = (1 - distance / maxDistance) * (0.095 + link.strength * 0.075) + pulse * 0.012
        const bend = Math.sin(link.phase + time * 0.00007) * 20
        const midX = (from.x + to.x) / 2 - dy / Math.max(distance, 1) * bend
        const midY = (from.y + to.y) / 2 + dx / Math.max(distance, 1) * bend
        const sameCluster = nodes[link.from].cluster === nodes[link.to].cluster
        const warmTrace = (nodes[link.from].cluster + nodes[link.to].cluster + link.from) % 6 === 0
        const baseTone = sameCluster
          ? (warmTrace
            ? (mode === 'light' ? LIGHT_NEURAL_PALETTE.emberRose : NEURAL_PALETTE.emberRose)
            : (mode === 'light' ? LIGHT_NEURAL_PALETTE.mutedIndigo : NEURAL_PALETTE.mutedIndigo))
          : (warmTrace
            ? (mode === 'light' ? LIGHT_NEURAL_PALETTE.agedGold : NEURAL_PALETTE.agedGold)
            : (mode === 'light' ? LIGHT_NEURAL_PALETTE.deepTeal : NEURAL_PALETTE.deepTeal))
        const mainTone = sameCluster
          ? (warmTrace ? NEURAL_PALETTE.agedGold : '117, 147, 204')
          : (warmTrace ? '174, 131, 86' : '88, 145, 123')
        ctx.beginPath()
        ctx.moveTo(from.x, from.y)
        ctx.quadraticCurveTo(midX, midY, to.x, to.y)
        ctx.strokeStyle = `rgba(${baseTone}, ${alpha * (sameCluster ? 0.42 : 0.36)})`
        ctx.lineWidth = sameCluster ? 2.2 : 1.65
        ctx.stroke()

        ctx.beginPath()
        ctx.moveTo(from.x, from.y)
        ctx.quadraticCurveTo(midX, midY, to.x, to.y)
        ctx.strokeStyle = `rgba(${mainTone}, ${alpha * (warmTrace ? 0.72 : 0.88)})`
        ctx.lineWidth = sameCluster ? 0.95 : 0.72
        ctx.stroke()
      }

      for (let index = 0; index < nodes.length; index++) {
        const node = nodes[index]
        const point = current[index]
        const pulse = REDUCED ? 0.35 : Math.sin(time * 0.00022 + node.phase) * 0.5 + 0.5
        const radius = node.size + pulse * 0.22
        const glow = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius * 5)
        const nodeTone = node.cluster === 3
          ? (mode === 'light' ? LIGHT_NEURAL_PALETTE.softViolet : NEURAL_PALETTE.softViolet)
          : (mode === 'light' ? LIGHT_NEURAL_PALETTE.nodeCore : NEURAL_PALETTE.nodeCore)
        const mutedTone = mode === 'light' ? LIGHT_NEURAL_PALETTE.mutedIndigo : NEURAL_PALETTE.mutedIndigo
        glow.addColorStop(0, `rgba(${nodeTone}, ${mode === 'light' ? 0.060 + node.depth * 0.030 : 0.036 + node.depth * 0.028})`)
        glow.addColorStop(0.45, `rgba(${mutedTone}, ${mode === 'light' ? 0.030 + node.depth * 0.016 : 0.018 + node.depth * 0.014})`)
        glow.addColorStop(1, `rgba(${mutedTone}, 0)`)
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(point.x, point.y, radius * 5, 0, Math.PI * 2)
        ctx.fill()

        ctx.beginPath()
        ctx.arc(point.x, point.y, radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${mode === 'light' ? LIGHT_NEURAL_PALETTE.nodeCore : NEURAL_PALETTE.nodeCore}, ${mode === 'light' ? 0.16 + node.depth * 0.08 : 0.07 + node.depth * 0.06})`
        ctx.fill()
      }

      ctx.restore()

      const veil = ctx.createRadialGradient(width * 0.48, height * 0.45, 0, width * 0.48, height * 0.45, Math.max(width, height) * 0.86)
      veil.addColorStop(0, mode === 'light' ? 'rgba(255, 255, 255, 0.10)' : 'rgba(0, 0, 0, 0.08)')
      veil.addColorStop(0.58, mode === 'light' ? 'rgba(255, 255, 255, 0.28)' : 'rgba(0, 0, 0, 0.40)')
      veil.addColorStop(1, mode === 'light' ? 'rgba(244, 247, 251, 0.74)' : 'rgba(0, 0, 0, 0.86)')
      ctx.fillStyle = veil
      ctx.fillRect(0, 0, width, height)

      if (!REDUCED) raf = requestAnimationFrame(draw)
    }

    resize()
    draw()
    const handleResize = () => {
      resize()
      if (REDUCED) draw()
    }
    window.addEventListener('resize', handleResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', handleResize)
    }
  }, [mode])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        background: mode === 'light' ? '#f4f7fb' : '#030507',
      }}
    />
  )
}

function FilamentInput({
  value,
  onChange,
  onKeyDown,
  type = 'text',
  placeholder,
  autoFocus,
  visible = true,
}: {
  value: string
  onChange: (v: string) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  type?: string
  placeholder?: string
  autoFocus?: boolean
  visible?: boolean
}) {
  const [focused, setFocused] = useState(false)
  const { mode } = useColorMode()
  const isLight = mode === 'light'
  const textColor = isLight ? '#0f172a' : '#f5f5f7'

  return (
    <motion.div
      initial={false}
      animate={visible ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      style={{ marginBottom: '3vh' }}
    >
      <Box sx={{ position: 'relative', width: 'clamp(260px, 16vw, 380px)' }}>
        <Box
          component="input"
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          sx={{
            width: '100%',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: textColor,
            caretColor: textColor,
            WebkitAppearance: 'none',
            fontSize: 'clamp(1.3rem, 1.6vw, 1.9rem)',
            textAlign: 'left',
            py: '1.6vh',
            px: 0.5,
            letterSpacing: '0.06em',
            fontFamily: 'inherit',
            '&::placeholder': {
              color: isLight ? 'rgba(15,23,42,0.56)' : 'rgba(255,255,255,0.38)',
              opacity: 1,
            },
            '&:-webkit-autofill, &:-webkit-autofill:hover, &:-webkit-autofill:focus': {
              WebkitTextFillColor: textColor,
              WebkitBoxShadow: `0 0 0 1000px ${isLight ? 'rgba(244, 247, 251, 0.01)' : 'rgba(3, 5, 7, 0.01)'} inset`,
              caretColor: textColor,
              transition: 'background-color 9999s ease-out 0s',
            },
            '&:autofill': {
              background: 'transparent',
              color: textColor,
            },
          }}
        />
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: focused ? '2px' : '1px',
            background: focused
              ? `linear-gradient(90deg, ${SIGNAL}, ${ACCENT}, ${WARM})`
              : (isLight ? 'rgba(15,23,42,0.34)' : 'rgba(255,255,255,0.26)'),
            transition: 'background 0.35s ease, height 0.35s ease',
            boxShadow: focused ? `0 6px 26px ${SIGNAL}35` : 'none',
          }}
        />
      </Box>
    </motion.div>
  )
}

function UnderlineCTA({
  loading,
  onClick,
  visible,
}: {
  loading: boolean
  onClick: () => void
  visible: boolean
}) {
  const { t } = useTranslation('common')
  const { mode } = useColorMode()
  const isLight = mode === 'light'

  return (
    <motion.div
      initial={false}
      animate={visible ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      style={{ textAlign: 'left', marginTop: 4, marginLeft: 4 }}
    >
      <Box
        component="button"
        type="button"
        onClick={onClick}
        disabled={loading}
        sx={{
          display: 'inline-block',
          background: 'transparent',
          border: 'none',
          color: loading
            ? (isLight ? 'rgba(15,23,42,0.36)' : 'rgba(255,255,255,0.40)')
            : (isLight ? '#0f172a' : '#f5f5f7'),
          fontSize: 'clamp(1.1rem, 1.3vw, 1.5rem)',
          fontWeight: 500,
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          cursor: loading ? 'default' : 'pointer',
          py: 0.5,
          px: 0,
          position: 'relative',
          opacity: loading ? 0.5 : 0.90,
          transition: 'opacity 0.2s ease',
          '&::after': {
            content: '""',
            position: 'absolute',
            left: '50%',
            bottom: 0,
            width: '100%',
            height: '1px',
            background: `linear-gradient(90deg, ${SIGNAL}, ${ACCENT}, ${WARM})`,
            transform: 'translateX(-50%) scaleX(0)',
            transformOrigin: 'center',
            transition: 'transform 0.35s ease',
          },
          '&:hover::after': {
            transform: 'translateX(-50%) scaleX(1)',
          },
        }}
      >
        {loading ? t('login.signingIn') : t('login.signIn')}
      </Box>
    </motion.div>
  )
}

export default function LoginPage() {
  const navigate = useNavigate()
  const notification = useNotification()
  const { setToken } = useAuthStore()
  const { mode } = useColorMode()
  const { t } = useTranslation('common')
  const isLight = mode === 'light'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    if (!username || !password) {
      notification.error(t('login.errorEmpty'))
      return
    }
    setLoading(true)
    try {
      const response = await adminAuthApi.login({ username, password })
      setToken(response.access_token)
      navigate('/')
    } catch (error) {
      notification.error(
        error instanceof Error ? error.message : t('login.errorFailed')
      )
    } finally {
      setLoading(false)
    }
  }

  const ctaVisible = Boolean(username && password)

  return (
    <Box sx={{ minHeight: '100vh', background: isLight ? '#f4f7fb' : '#030507', position: 'relative', overflow: 'hidden' }}>
      <CortexFieldBackground mode={mode} />

      <Box sx={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none' }}>
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={REDUCED ? { duration: 0.4 } : { type: 'spring', stiffness: 180, damping: 22 }}
          style={{
            position: 'absolute',
            left: '7vw',
            top: '10vh',
            pointerEvents: 'auto',
          }}
        >
          <Box
            component="img"
            src={mode === 'dark' ? logoDarkUrl : logoLightUrl}
            alt="HCZ"
            sx={{
              width: '27vw',
              height: '27vw',
              minWidth: 180,
              minHeight: 180,
              maxWidth: 520,
              maxHeight: 520,
              display: 'block',
              opacity: isLight ? 0.88 : 1,
              filter: isLight
                ? 'drop-shadow(0 22px 34px rgba(15,23,42,0.16))'
                : `drop-shadow(0 0 28px ${ACCENT}40) drop-shadow(0 0 60px ${SIGNAL}22)`,
            }}
          />
        </motion.div>

        <Box
          sx={{
            position: 'absolute',
            left: '42vw',
            top: '40vh',
            pointerEvents: 'auto',
          }}
        >
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={REDUCED ? { duration: 0.4, delay: 0.2 } : { duration: 0.6, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <Box
              sx={{
                fontFamily: "'Inter', sans-serif",
                fontWeight: 700,
                fontSize: 'clamp(2rem, 2.8vw, 3.2rem)',
                letterSpacing: '0.28em',
                textTransform: 'uppercase',
                color: isLight ? 'rgba(15,23,42,0.88)' : 'rgba(255,255,255,0.52)',
                ml: '-1vw',
                textShadow: isLight ? '0 1px 0 rgba(255,255,255,0.88), 0 18px 36px rgba(15,23,42,0.10)' : `
                  0 0 2px rgba(255,255,255,0.55),
                  0 0 6px rgba(255,255,255,0.38),
                  0 0 14px rgba(92,157,255,0.42),
                  0 0 28px rgba(92,157,255,0.28)
                `,
              }}
            >
              Holo Cortex Zero
            </Box>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={REDUCED ? { duration: 0.4, delay: 0.35 } : { duration: 0.6, delay: 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            <Box
              sx={{
                fontFamily: "'Inter', sans-serif",
                fontStyle: 'italic',
                fontWeight: 400,
                fontSize: 'clamp(1.2rem, 1.5vw, 1.8rem)',
                letterSpacing: '0.08em',
                color: isLight ? 'rgba(15,23,42,0.66)' : 'rgba(255,255,255,0.35)',
                mt: '1.5vh',
                textShadow: isLight ? 'none' : '0 0 6px rgba(255,255,255,0.18), 0 0 16px rgba(92,157,255,0.14)',
              }}
          >
            From the depth of the Holo Cortex, emergence starts at Zero
          </Box>
        </motion.div>
        </Box>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={REDUCED ? { duration: 0.4, delay: 0.5 } : { duration: 0.6, delay: 0.8, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: 'absolute',
            right: '12vw',
            bottom: '5vh',
            pointerEvents: 'auto',
          }}
        >
          <FilamentInput
            placeholder="IDENTITY"
            value={username}
            onChange={setUsername}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            autoFocus
          />

          <FilamentInput
            type="password"
            placeholder="PASSCODE"
            value={password}
            onChange={setPassword}
            onKeyDown={e => e.key === 'Enter' && handleLogin()}
            visible={Boolean(username)}
          />

          <UnderlineCTA
            loading={loading}
            onClick={handleLogin}
            visible={ctaVisible}
          />
        </motion.div>
      </Box>
    </Box>
  )
}
