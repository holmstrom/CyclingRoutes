"use client";

const DIRECTIONS = [
  { name: "north", label: "N", angle: 0 },
  { name: "northeast", label: "NE", angle: 45 },
  { name: "east", label: "E", angle: 90 },
  { name: "southeast", label: "SE", angle: 135 },
  { name: "south", label: "S", angle: 180 },
  { name: "southwest", label: "SW", angle: 225 },
  { name: "west", label: "W", angle: 270 },
  { name: "northwest", label: "NW", angle: 315 },
];

interface CompassRoseProps {
  selected: string | null;
  onSelect: (direction: string | null) => void;
}

export default function CompassRose({ selected, onSelect }: CompassRoseProps) {
  const radius = 52;
  const center = 64;

  return (
    <div className="flex flex-col items-center gap-1">
      <label className="text-xs text-gray-400 uppercase tracking-wider">
        Direction
      </label>
      <svg width={128} height={128} viewBox="0 0 128 128">
        {/* Background circle */}
        <circle
          cx={center}
          cy={center}
          r={radius + 4}
          fill="rgba(255,255,255,0.03)"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={1}
        />

        {/* Direction buttons */}
        {DIRECTIONS.map((dir) => {
          const rad = ((dir.angle - 90) * Math.PI) / 180;
          const x = center + radius * Math.cos(rad);
          const y = center + radius * Math.sin(rad);
          const isSelected = selected === dir.name;

          return (
            <g
              key={dir.name}
              onClick={() => onSelect(isSelected ? null : dir.name)}
              className="cursor-pointer"
            >
              <circle
                cx={x}
                cy={y}
                r={14}
                fill={isSelected ? "#3b82f6" : "rgba(255,255,255,0.06)"}
                stroke={isSelected ? "#60a5fa" : "rgba(255,255,255,0.15)"}
                strokeWidth={1.5}
                className="transition-all duration-200 hover:fill-[rgba(255,255,255,0.12)]"
              />
              <text
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="central"
                fill={isSelected ? "white" : "#9ca3af"}
                fontSize={10}
                fontWeight={isSelected ? 700 : 500}
                className="select-none pointer-events-none"
              >
                {dir.label}
              </text>
            </g>
          );
        })}

        {/* Center "Any" button */}
        <g
          onClick={() => onSelect(null)}
          className="cursor-pointer"
        >
          <circle
            cx={center}
            cy={center}
            r={18}
            fill={selected === null ? "#3b82f6" : "rgba(255,255,255,0.04)"}
            stroke={selected === null ? "#60a5fa" : "rgba(255,255,255,0.1)"}
            strokeWidth={1.5}
            className="transition-all duration-200"
          />
          <text
            x={center}
            y={center}
            textAnchor="middle"
            dominantBaseline="central"
            fill={selected === null ? "white" : "#6b7280"}
            fontSize={9}
            fontWeight={500}
            className="select-none pointer-events-none"
          >
            ANY
          </text>
        </g>
      </svg>
    </div>
  );
}
