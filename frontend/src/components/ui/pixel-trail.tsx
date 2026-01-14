"use client"
import React, { useEffect, useRef, useState, useCallback } from "react"

interface Pixel {
    id: number
    x: number
    y: number
    opacity: number
    age: number
}

const PIXEL_SIZE = 12
const TRAIL_LENGTH = 40
const FADE_SPEED = 0.04

export function PixelCursorTrail() {
    const containerRef = useRef<HTMLDivElement>(null)
    const [pixels, setPixels] = useState<Pixel[]>([])
    const pixelIdRef = useRef(0)
    const lastPositionRef = useRef({ x: 0, y: 0 })
    const animationRef = useRef<number | undefined>(undefined)

    const createPixel = useCallback((x: number, y: number) => {
        return {
            id: pixelIdRef.current++,
            x,
            y,
            opacity: 1,
            age: 0,
        }
    }, [])

    const handleMouseMove = useCallback(
        (e: MouseEvent) => {
            const x = e.clientX
            const y = e.clientY

            const dx = x - lastPositionRef.current.x
            const dy = y - lastPositionRef.current.y
            const distance = Math.sqrt(dx * dx + dy * dy)

            // Increased threshold slightly for performance
            if (distance > 18) {
                const newPixel = createPixel(x, y)
                setPixels((prev) => [...prev.slice(-TRAIL_LENGTH), newPixel])
                lastPositionRef.current = { x, y }
            }
        },
        [createPixel],
    )

    useEffect(() => {
        let lastTime = 0;
        const animate = (time: number) => {
            // Cap at ~60fps for stability during scroll
            if (time - lastTime > 16) {
                setPixels((prev) =>
                    prev
                        .map((pixel) => ({
                            ...pixel,
                            opacity: pixel.opacity - FADE_SPEED,
                            age: pixel.age + 1,
                        }))
                        .filter((pixel) => pixel.opacity > 0),
                )
                lastTime = time;
            }
            animationRef.current = requestAnimationFrame(animate)
        }

        animationRef.current = requestAnimationFrame(animate)
        window.addEventListener("mousemove", handleMouseMove, { passive: true })

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
            window.removeEventListener("mousemove", handleMouseMove)
        }
    }, [handleMouseMove])

    return (
        <div
            className="fixed inset-0 pointer-events-none z-[99999]"
            style={{ overflow: 'hidden' }}
        >
            {pixels.map((pixel) => {
                // Calculate size based on age - older pixels are smaller
                const sizeMultiplier = Math.max(0.3, 1 - pixel.age / 100)
                const currentSize = PIXEL_SIZE * sizeMultiplier

                return (
                    <div
                        key={pixel.id}
                        className="absolute bg-white"
                        style={{
                            left: pixel.x - currentSize / 2,
                            top: pixel.y - currentSize / 2,
                            width: currentSize,
                            height: currentSize,
                            opacity: pixel.opacity * 0.5, // Reduced base opacity for subtlety
                            transition: "width 0.1s ease-out, height 0.1s ease-out",
                        }}
                    />
                )
            })}
        </div>
    )
}
