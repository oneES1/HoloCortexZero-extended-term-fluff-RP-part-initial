import type { CSSProperties, Dispatch, ReactNode, SetStateAction } from 'react'
import {
  Box,
  Button,
  FormControlLabel,
  TableCell,
  TableRow,
  TextField,
  Typography,
  Switch,
  type SxProps,
  type Theme,
} from '@mui/material'
import type { TFunction } from 'i18next'
import type { ConfigItem, ExpandedRowsState, FieldSchema } from './types'

export function renderSimpleListInput(
  value: unknown,
  elementType: string,
  onChange: (value: unknown) => void,
  t: TFunction
): ReactNode {
  switch (elementType) {
    case 'bool':
      return (
        <FormControlLabel
          control={
            <Switch
              checked={Boolean(value)}
              onChange={e => onChange(e.target.checked)}
              size="small"
              color="primary"
            />
          }
          label={value ? t('common.yes') : t('common.no')}
        />
      )
    case 'int':
    case 'float':
      return (
        <TextField
          type="number"
          value={value || ''}
          onChange={e =>
            onChange(
              elementType === 'int'
                ? parseInt(e.target.value, 10) || 0
                : parseFloat(e.target.value) || 0
            )
          }
          size="small"
          fullWidth
          variant="outlined"
        />
      )
    default:
      return (
        <TextField
          value={String(value || '')}
          onChange={e => onChange(e.target.value)}
          size="small"
          fullWidth
          variant="outlined"
        />
      )
  }
}

export function renderFieldInput(
  value: unknown,
  fieldSchema: FieldSchema,
  onChange: (value: unknown) => void,
  t: TFunction,
  fieldKey?: string,
  expandedRows?: ExpandedRowsState,
  setExpandedRows?: Dispatch<SetStateAction<ExpandedRowsState>>
): ReactNode {
  switch (fieldSchema.type) {
    case 'bool':
    case 'boolean':
      return (
        <FormControlLabel
          control={
            <Switch
              checked={Boolean(value)}
              onChange={e => onChange(e.target.checked)}
              size="small"
              color="primary"
            />
          }
          label={value ? t('common.yes') : t('common.no')}
        />
      )
    case 'int':
    case 'float':
    case 'number':
      return (
        <TextField
          type="number"
          value={value || ''}
          onChange={e =>
            onChange(
              fieldSchema.type === 'int'
                ? parseInt(e.target.value, 10) || 0
                : parseFloat(e.target.value) || 0
            )
          }
          size="small"
          fullWidth
          placeholder={fieldSchema.placeholder}
          variant="outlined"
        />
      )
    case 'list': {
      if (fieldKey && expandedRows && setExpandedRows) {
        const listValue = Array.isArray(value) ? value : []
        const isExpanded = expandedRows[fieldKey] || false

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <TextField
              value={t('configTable.listCount', { count: listValue.length })}
              size="small"
              fullWidth
              InputProps={{
                readOnly: true,
                sx: {
                  cursor: 'pointer',
                  bgcolor: 'transparent',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                },
              }}
              onClick={() => setExpandedRows(prev => ({ ...prev, [fieldKey]: !prev[fieldKey] }))}
              variant="outlined"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '&:hover .MuiOutlinedInput-notchedOutline': {
                    borderColor: 'primary.main',
                  },
                },
              }}
            />
            <Button
              size="small"
              onClick={() => setExpandedRows(prev => ({ ...prev, [fieldKey]: !prev[fieldKey] }))}
              sx={{
                flexShrink: 0,
                textTransform: 'none',
                minWidth: 0,
                px: 1,
                fontSize: '0.75rem',
                color: 'text.secondary',
              }}
            >
              {isExpanded ? t('configTable.collapse') : t('configTable.expand')}
            </Button>
          </Box>
        )
      }

      const listValue = Array.isArray(value) ? value : []
      return (
        <TextField
          value={t('configTable.listCount', { count: listValue.length })}
          size="small"
          fullWidth
          InputProps={{ readOnly: true }}
          variant="outlined"
        />
      )
    }
    default:
      return (
        <TextField
          type="text"
          value={String(value || '')}
          onChange={e => onChange(e.target.value)}
          size="small"
          fullWidth
          placeholder={fieldSchema.placeholder}
          variant="outlined"
          multiline={fieldSchema.is_textarea}
          minRows={fieldSchema.is_textarea ? 2 : 1}
          maxRows={fieldSchema.is_textarea ? 4 : 1}
          InputProps={{
            style: fieldSchema.is_secret
              ? ({
                  '-webkit-text-security': 'disc',
                  'text-security': 'disc',
                } as CSSProperties)
              : undefined,
          }}
        />
      )
  }
}

export function getDefaultValueForType(type: string): unknown {
  switch (type) {
    case 'bool':
    case 'boolean':
      return false
    case 'int':
    case 'float':
    case 'number':
      return 0
    case 'list':
      return []
    case 'dict':
      return {}
    default:
      return ''
  }
}

export function renderNestedConfigRows(
  config: ConfigItem,
  editingValues: Record<string, string>,
  handleConfigChange: (key: string, value: string) => void,
  isSmall: boolean,
  expandedRows: ExpandedRowsState,
  setExpandedRows: Dispatch<SetStateAction<ExpandedRowsState>>,
  t: TFunction,
  level: number = 0,
  parentKey: string = ''
): ReactNode[] {
  const rows: ReactNode[] = []
  let currentValue
  try {
    currentValue =
      editingValues[config.key] !== undefined ? JSON.parse(editingValues[config.key]) : config.value
  } catch {
    currentValue = config.value
  }

  const tableCellStyle: SxProps<Theme> = {
    py: isSmall ? 0.55 : 0.9,
    px: 1.5,
    pl: 2 + level * 2,
    verticalAlign: 'top',
    borderLeft: level > 0 ? `2px solid` : 'none',
    borderLeftColor: level > 0 ? 'divider' : 'transparent',
  }

  if (config.type === 'list' && !config.is_complex) {
    const listValue = Array.isArray(currentValue) ? currentValue : []
    const elementType = config.element_type || 'str'

    listValue.forEach((item: unknown, index: number) => {
      const subKey = `${parentKey}${config.key}[${index}]`
      rows.push(
        <TableRow key={subKey}>
          <TableCell sx={tableCellStyle}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ fontSize: isSmall ? '0.75rem' : 'inherit' }}>
                {config.sub_item_name ? `${config.sub_item_name}[${index}]` : `[${index}]`}
              </Typography>
              <Button
                size="small"
                onClick={() => {
                  const newList = listValue.filter((_, i) => i !== index)
                  handleConfigChange(config.key, JSON.stringify(newList))
                }}
                sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem', color: 'text.secondary', '&:hover': { color: 'error.main' } }}
              >
                {t('actions.remove')}
              </Button>
            </Box>
          </TableCell>
          <TableCell>
            {renderSimpleListInput(
              item,
              elementType,
              newValue => {
                const newList = [...listValue]
                newList[index] = newValue
                handleConfigChange(config.key, JSON.stringify(newList))
              },
              t
            )}
          </TableCell>
        </TableRow>
      )
    })
    rows.push(
      <TableRow key={`${config.key}-add`}>
        <TableCell sx={tableCellStyle} colSpan={2}>
          <Button
            variant="text"
            size="small"
            onClick={() => {
              const defaultValue = getDefaultValueForType(elementType)
              const newList = [...listValue, defaultValue]
              handleConfigChange(config.key, JSON.stringify(newList))
            }}
            sx={{ color: 'primary.main' }}
          >
            {t('configTable.addNewItem', {
              name: config.sub_item_name || t('common.item', { defaultValue: 'Item' }),
            })}
          </Button>
        </TableCell>
      </TableRow>
    )
  }

  if (config.is_complex && config.type === 'list') {
    const listValue = Array.isArray(currentValue) ? currentValue : []
    listValue.forEach((item: unknown, index: number) => {
      const itemValue =
        typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : {}
      const subKey = `${parentKey}${config.key}[${index}]`
      rows.push(
        <TableRow key={subKey}>
          <TableCell sx={tableCellStyle}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ fontSize: isSmall ? '0.75rem' : 'inherit' }}>
                {config.sub_item_name ? `${config.sub_item_name}[${index}]` : `[${index}]`}
              </Typography>
              <Button
                size="small"
                onClick={() => {
                  const newList = listValue.filter((_, i) => i !== index)
                  handleConfigChange(config.key, JSON.stringify(newList))
                }}
                sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem', color: 'text.secondary', '&:hover': { color: 'error.main' } }}
              >
                {t('actions.remove')}
              </Button>
            </Box>
          </TableCell>
          <TableCell>
            <TextField
              value={t('configTable.objectCount', {
                count: Object.keys(itemValue).length,
              })}
              size="small"
              fullWidth
              InputProps={{ readOnly: true }}
              variant="outlined"
            />
          </TableCell>
        </TableRow>
      )

      if (config.field_schema) {
        Object.entries(config.field_schema).forEach(([fieldName, fieldSchema]) => {
          const fieldKey = `${subKey}.${fieldName}`
          const fieldValue = itemValue[fieldName]
          rows.push(
            <TableRow key={fieldKey}>
              <TableCell sx={{ ...tableCellStyle, pl: 4 + level * 2 }}>
                <Typography variant="body2" sx={{ fontSize: isSmall ? '0.75rem' : 'inherit' }}>
                  {fieldSchema.title || fieldName}
                </Typography>
              </TableCell>
              <TableCell>
                {renderFieldInput(
                  fieldValue,
                  fieldSchema,
                  newValue => {
                    const newList = [...listValue]
                    const newItem = { ...(newList[index] as Record<string, unknown>) }
                    newItem[fieldName] = newValue
                    newList[index] = newItem
                    handleConfigChange(config.key, JSON.stringify(newList))
                  },
                  t,
                  fieldSchema.type === 'list' ? fieldKey : undefined,
                  expandedRows,
                  setExpandedRows
                )}
              </TableCell>
            </TableRow>
          )

          if (fieldSchema.type === 'list' && expandedRows[fieldKey]) {
            const fieldListValue = Array.isArray(fieldValue) ? fieldValue : []
            const fieldElementType = fieldSchema.element_type || 'str'
            fieldListValue.forEach((listItem: unknown, listIndex: number) => {
              rows.push(
                <TableRow
                  key={`${fieldKey}[${listIndex}]`}
                                 >
                  <TableCell sx={{ ...tableCellStyle, pl: 6 + level * 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" sx={{ fontSize: isSmall ? '0.75rem' : 'inherit' }}>
                        [{listIndex}]
                      </Typography>
                      <Button
                        size="small"
                        onClick={() => {
                          const newFieldList = fieldListValue.filter((_, i) => i !== listIndex)
                          const newList = [...listValue]
                          const newItem = { ...(newList[index] as Record<string, unknown>) }
                          newItem[fieldName] = newFieldList
                          newList[index] = newItem
                          handleConfigChange(config.key, JSON.stringify(newList))
                        }}
                        sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem', color: 'text.secondary', '&:hover': { color: 'error.main' } }}
                      >
                        {t('actions.remove')}
                      </Button>
                    </Box>
                  </TableCell>
                  <TableCell>
                    {renderSimpleListInput(
                      listItem,
                      fieldElementType,
                      newValue => {
                        const newFieldList = [...fieldListValue]
                        newFieldList[listIndex] = newValue
                        const newList = [...listValue]
                        const newItem = { ...(newList[index] as Record<string, unknown>) }
                        newItem[fieldName] = newFieldList
                        newList[index] = newItem
                        handleConfigChange(config.key, JSON.stringify(newList))
                      },
                      t
                    )}
                  </TableCell>
                </TableRow>
              )
            })
            rows.push(
              <TableRow key={`${subKey}-add`}>
                <TableCell sx={{ ...tableCellStyle, pl: 6 + level * 2 }} colSpan={2}>
                  <Button
                    variant="text"
                    size="small"
                    onClick={() => {
                      const defaultValue = getDefaultValueForType(fieldElementType)
                      const newFieldList = [...fieldListValue, defaultValue]
                      const newList = [...listValue]
                      const newItem = { ...(newList[index] as Record<string, unknown>) }
                      newItem[fieldName] = newFieldList
                      newList[index] = newItem
                      handleConfigChange(config.key, JSON.stringify(newList))
                    }}
                    sx={{ color: 'primary.main' }}
                  >
                    {t('configTable.addItem', { name: fieldSchema.title || fieldName })}
                  </Button>
                </TableCell>
              </TableRow>
            )
          }
        })
      }
    })
    rows.push(
      <TableRow key={`${config.key}-add-complex`}>
        <TableCell sx={tableCellStyle} colSpan={2}>
          <Button
            variant="text"
            size="small"
            onClick={() => {
              const newItem: Record<string, unknown> = {}
              if (config.field_schema) {
                Object.entries(config.field_schema).forEach(([fieldName, fieldSchema]) => {
                  newItem[fieldName] =
                    fieldSchema.default ?? getDefaultValueForType(fieldSchema.type)
                })
              }
              const newList = [...listValue, newItem]
              handleConfigChange(config.key, JSON.stringify(newList))
            }}
            sx={{ color: 'primary.main' }}
          >
            {t('configTable.addNewItem', {
              name: config.sub_item_name || t('common.item', { defaultValue: 'Item' }),
            })}
          </Button>
        </TableCell>
      </TableRow>
    )
  }

  if (config.type === 'dict' && !config.is_complex) {
    const dictValue =
      currentValue && typeof currentValue === 'object'
        ? (currentValue as Record<string, unknown>)
        : {}
    const valueType = config.value_type || 'str'
    Object.entries(dictValue).forEach(([key, value]) => {
      rows.push(
        <TableRow key={`${config.key}.${key}`}>
          <TableCell sx={tableCellStyle}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ fontSize: isSmall ? '0.75rem' : 'inherit' }}>
                {key}
              </Typography>
              <Button
                size="small"
                onClick={() => {
                  const newDict = { ...dictValue }
                  delete newDict[key]
                  handleConfigChange(config.key, JSON.stringify(newDict))
                }}
                sx={{ textTransform: 'none', minWidth: 0, px: 0.5, fontSize: '0.7rem', color: 'text.secondary', '&:hover': { color: 'error.main' } }}
              >
                {t('actions.remove')}
              </Button>
            </Box>
          </TableCell>
          <TableCell>
            {renderSimpleListInput(
              value,
              valueType,
              newValue => {
                const newDict = { ...dictValue, [key]: newValue }
                handleConfigChange(config.key, JSON.stringify(newDict))
              },
              t
            )}
          </TableCell>
        </TableRow>
      )
    })
    rows.push(
      <TableRow key={`${config.key}-add-dict`}>
        <TableCell sx={tableCellStyle} colSpan={2}>
          <TextField
            size="small"
            placeholder={t('configTable.newItemPlaceholder')}
            variant="outlined"
            onKeyPress={e => {
              if (e.key === 'Enter') {
                const target = e.target as HTMLInputElement
                const newKey = target.value.trim()
                if (newKey && !dictValue[newKey]) {
                  const defaultValue = getDefaultValueForType(valueType)
                  const newDict = { ...dictValue, [newKey]: defaultValue }
                  handleConfigChange(config.key, JSON.stringify(newDict))
                  target.value = ''
                }
              }
            }}
            sx={{ width: '200px' }}
          />
        </TableCell>
      </TableRow>
    )
  }

  return rows
}
