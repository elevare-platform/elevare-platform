import { useEffect, useRef } from 'react'

export default function TalentGraphCanvas({ className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId = null
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth)
    let height = (canvas.height = canvas.parentElement?.clientHeight || window.innerHeight)

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return
      width = canvas.width = canvas.parentElement.clientWidth
      height = canvas.height = canvas.parentElement.clientHeight
    }

    window.addEventListener('resize', handleResize)

    // Mouse position tracking for subtle attraction
    const mouse = { x: -1000, y: -1000, radius: 140 }

    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
    }

    const handleMouseLeave = () => {
      mouse.x = -1000
      mouse.y = -1000
    }

    canvas.parentElement?.addEventListener('mousemove', handleMouseMove)
    canvas.parentElement?.addEventListener('mouseleave', handleMouseLeave)

    // Minimalist, crisp node graph configuration
    const NODE_COUNT = Math.min(48, Math.floor((width * height) / 22000))
    const nodes = []

    const COLORS = [
      { r: 26, g: 77, b: 143 },   // Elevare Royal Blue
      { r: 232, g: 119, b: 34 },  // Elevare Warm Amber
      { r: 148, g: 163, b: 184 }, // Slate 400
    ]

    for (let i = 0; i < NODE_COUNT; i++) {
      const color = COLORS[Math.floor(Math.random() * COLORS.length)]
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        radius: Math.random() * 1.5 + 1.0,
        color,
      })
    }

    let isTabVisible = !document.hidden

    const render = () => {
      if (!isTabVisible) return

      ctx.clearRect(0, 0, width, height)

      const maxDistance = 130

      for (let i = 0; i < nodes.length; i++) {
        const nodeA = nodes[i]

        nodeA.x += nodeA.vx
        nodeA.y += nodeA.vy

        if (nodeA.x < 0 || nodeA.x > width) nodeA.vx *= -1
        if (nodeA.y < 0 || nodeA.y > height) nodeA.vy *= -1

        // Mouse attraction
        const dxMouse = mouse.x - nodeA.x
        const dyMouse = mouse.y - nodeA.y
        const distMouse = Math.sqrt(dxMouse * dxMouse + dyMouse * dyMouse)
        if (distMouse < mouse.radius) {
          const force = (mouse.radius - distMouse) / mouse.radius
          nodeA.x += (dxMouse / distMouse) * force * 0.5
          nodeA.y += (dyMouse / distMouse) * force * 0.5
        }

        // Draw connections
        for (let j = i + 1; j < nodes.length; j++) {
          const nodeB = nodes[j]
          const dx = nodeA.x - nodeB.x
          const dy = nodeA.y - nodeB.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < maxDistance) {
            const alpha = (1 - dist / maxDistance) * 0.18
            ctx.beginPath()
            ctx.moveTo(nodeA.x, nodeA.y)
            ctx.lineTo(nodeB.x, nodeB.y)
            ctx.strokeStyle = `rgba(${nodeA.color.r}, ${nodeA.color.g}, ${nodeA.color.b}, ${alpha})`
            ctx.lineWidth = 0.75
            ctx.stroke()
          }
        }

        // Draw node dot
        ctx.beginPath()
        ctx.arc(nodeA.x, nodeA.y, nodeA.radius, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${nodeA.color.r}, ${nodeA.color.g}, ${nodeA.color.b}, 0.65)`
        ctx.fill()
      }

      animationFrameId = requestAnimationFrame(render)
    }

    const handleVisibilityChange = () => {
      isTabVisible = !document.hidden
      if (isTabVisible) {
        render()
      } else if (animationFrameId) {
        cancelAnimationFrame(animationFrameId)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    render()

    return () => {
      window.removeEventListener('resize', handleResize)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      if (canvas.parentElement) {
        canvas.parentElement.removeEventListener('mousemove', handleMouseMove)
        canvas.parentElement.removeEventListener('mouseleave', handleMouseLeave)
      }
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId)
      }
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 pointer-events-none z-0 ${className}`}
      aria-hidden="true"
    />
  )
}
