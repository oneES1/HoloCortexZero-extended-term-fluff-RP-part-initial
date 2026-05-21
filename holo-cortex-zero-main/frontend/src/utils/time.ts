export function formatTimestampToTime(timestamp: string | number): string {
  let date: Date

  if (typeof timestamp === 'number') {
    date = new Date(timestamp)
  } else {
    // 如果是纯数字字符串（Unix时间戳），转换为数字
    if (/^\d+$/.test(timestamp)) {
      date = new Date(parseInt(timestamp, 10))
    } else {
      // ISO格式或其他日期字符串直接解析
      date = new Date(timestamp)
    }
  }

  // 检查日期是否有效
  if (isNaN(date.getTime())) {
    return 'Invalid Time'
  }

  // 格式化时间 HH:MM:SS
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')

  return `${hours}:${minutes}:${seconds}`
}

function parseTimestamp(timestamp: string | number): Date | null {
  let date: Date

  if (typeof timestamp === 'number') {
    date = new Date(timestamp)
  } else if (/^\d+$/.test(timestamp)) {
    date = new Date(parseInt(timestamp, 10))
  } else {
    date = new Date(timestamp)
  }

  if (isNaN(date.getTime())) {
    return null
  }

  return date
}

function padTimeUnit(value: number): string {
  return value.toString().padStart(2, '0')
}

export function formatTimestampByGranularity(
  timestamp: string | number,
  granularityMinutes: number
): string {
  const date = parseTimestamp(timestamp)

  if (!date) {
    return 'Invalid Time'
  }

  const month = padTimeUnit(date.getMonth() + 1)
  const day = padTimeUnit(date.getDate())
  const hours = padTimeUnit(date.getHours())
  const minutes = padTimeUnit(date.getMinutes())

  if (granularityMinutes <= 60) {
    return `${hours}:${minutes}`
  }

  if (granularityMinutes <= 60 * 24) {
    return `${month}-${day} ${hours}:${minutes}`
  }

  return `${month}-${day}`
}

export function formatTimestampToDateTime(timestamp: string | number): string {
  const date = parseTimestamp(timestamp)

  if (!date) {
    return 'Invalid Time'
  }

  const year = date.getFullYear()
  const month = padTimeUnit(date.getMonth() + 1)
  const day = padTimeUnit(date.getDate())
  const hours = padTimeUnit(date.getHours())
  const minutes = padTimeUnit(date.getMinutes())
  const seconds = padTimeUnit(date.getSeconds())

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}
