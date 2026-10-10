import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { prefersReducedMotion } from '../lib/motion'

const GRID = 'rgba(148, 163, 184, 0.08)'
const AXIS_TICK = {
  fill: '#64748b',
  fontSize: 11,
  fontFamily: 'Fira Code, monospace',
}

function ChartTip({ active, payload, label, unit = 'observations' }) {
  if (!active || !payload || !payload.length) return null

  return (
    <div className="cam-tooltip">
      <strong>{label}</strong>
      <span className="cam-tooltip__meta">
        {payload[0].value} {unit}
      </span>
    </div>
  )
}

export function HourlyChart({ data }) {
  const animate = !prefersReducedMotion()

  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <defs>
          <linearGradient id="hourFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity={0.32} />
            <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="hour"
          tickFormatter={(hour) => `${String(hour).padStart(2, '0')}`}
          tick={AXIS_TICK}
          axisLine={false}
          tickLine={false}
          interval={2}
        />
        <YAxis
          tick={AXIS_TICK}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
          width={34}
        />
        <Tooltip
          content={<ChartTip />}
          cursor={{ stroke: 'rgba(148, 163, 184, 0.25)' }}
        />
        <Area
          type="monotone"
          dataKey="observations"
          stroke="#22c55e"
          strokeWidth={2}
          fill="url(#hourFill)"
          isAnimationActive={animate}
          animationDuration={700}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function CameraChart({ data }) {
  const animate = !prefersReducedMotion()

  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 4, right: 34, left: 4, bottom: 0 }}
      >
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="camera_id"
          width={62}
          tick={{ ...AXIS_TICK, fontSize: 11.5 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={<ChartTip />}
          cursor={{ fill: 'rgba(148, 163, 184, 0.06)' }}
        />
        <Bar
          dataKey="observations"
          fill="#38bdf8"
          radius={[0, 4, 4, 0]}
          barSize={16}
          isAnimationActive={animate}
          animationDuration={700}
        >
          <LabelList
            dataKey="observations"
            position="right"
            style={{
              fill: '#e8eef7',
              fontFamily: 'Fira Code, monospace',
              fontSize: 11.5,
            }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DailyChart({ data }) {
  const animate = !prefersReducedMotion()

  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={data} margin={{ top: 8, right: 10, left: -22, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={(value) => value.slice(5)}
          tick={AXIS_TICK}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={AXIS_TICK}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
          width={34}
        />
        <Tooltip
          content={<ChartTip />}
          cursor={{ stroke: 'rgba(148, 163, 184, 0.25)' }}
        />
        <Line
          type="monotone"
          dataKey="observations"
          stroke="#a78bfa"
          strokeWidth={2}
          dot={{ r: 3, fill: '#a78bfa', strokeWidth: 0 }}
          activeDot={{ r: 5 }}
          isAnimationActive={animate}
          animationDuration={700}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
