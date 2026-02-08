import React from 'react'

interface SimpleMarkdownProps {
  content: string
}

export function SimpleMarkdown({ content }: SimpleMarkdownProps) {
  const renderMarkdown = (text: string) => {
    const lines = text.split('\n')
    const elements: React.JSX.Element[] = []
    let i = 0
    let inCodeBlock = false
    let codeContent: string[] = []
    let inTable = false
    let tableRows: string[][] = []

    while (i < lines.length) {
      const line = lines[i]

      // Code block
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <pre key={`code-${i}`} className="bg-gray-800 p-3 rounded text-xs overflow-x-auto my-2 font-mono text-gray-300">
              {codeContent.join('\n')}
            </pre>
          )
          codeContent = []
          inCodeBlock = false
        } else {
          inCodeBlock = true
        }
        i++
        continue
      }

      if (inCodeBlock) {
        codeContent.push(line)
        i++
        continue
      }

      // Table
      if (line.startsWith('|')) {
        if (!inTable) {
          inTable = true
          tableRows = []
        }
        // Skip separator rows
        if (!line.match(/^\|[\s\-:|]+\|$/)) {
          const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim())
          tableRows.push(cells)
        }
        i++
        continue
      } else if (inTable) {
        elements.push(
          <div key={`table-${i}`} className="overflow-x-auto my-2">
            <table className="text-xs border-collapse w-full">
              <tbody>
                {tableRows.map((row, rowIdx) => (
                  <tr key={rowIdx} className={rowIdx === 0 ? 'bg-gray-800 font-medium' : 'border-t border-gray-700'}>
                    {row.map((cell, cellIdx) => (
                      <td key={cellIdx} className="px-2 py-1 text-gray-300">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        tableRows = []
        inTable = false
        continue
      }

      // Horizontal rule
      if (line.match(/^[-=]{3,}$/)) {
        elements.push(<hr key={`hr-${i}`} className="border-gray-700 my-3" />)
        i++
        continue
      }

      // Headers
      if (line.startsWith('## ')) {
        elements.push(
          <h3 key={`h3-${i}`} className="text-sm font-semibold text-math-purple mt-4 mb-2">
            {line.slice(3)}
          </h3>
        )
        i++
        continue
      }
      if (line.startsWith('### ')) {
        elements.push(
          <h4 key={`h4-${i}`} className="text-xs font-medium text-gray-300 mt-3 mb-1">
            {line.slice(4)}
          </h4>
        )
        i++
        continue
      }

      // Warning/emphasis
      if (line.startsWith('⚠️') || line.startsWith('═')) {
        elements.push(
          <div key={`warn-${i}`} className="text-xs text-yellow-500 font-medium my-2">
            {line}
          </div>
        )
        i++
        continue
      }

      // List items
      if (line.startsWith('- ')) {
        elements.push(
          <div key={`li-${i}`} className="text-xs text-gray-400 pl-3 my-0.5">
            • {line.slice(2)}
          </div>
        )
        i++
        continue
      }

      // Empty line
      if (line.trim() === '') {
        elements.push(<div key={`empty-${i}`} className="h-2" />)
        i++
        continue
      }

      // Regular text
      elements.push(
        <p key={`p-${i}`} className="text-xs text-gray-400 my-1">
          {line}
        </p>
      )
      i++
    }

    // Flush remaining table
    if (inTable && tableRows.length > 0) {
      elements.push(
        <div key="final-table" className="overflow-x-auto my-2">
          <table className="text-xs border-collapse w-full">
            <tbody>
              {tableRows.map((row, rowIdx) => (
                <tr key={rowIdx} className={rowIdx === 0 ? 'bg-gray-800 font-medium' : 'border-t border-gray-700'}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className="px-2 py-1 text-gray-300">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }

    return elements
  }

  return <div className="markdown-content">{renderMarkdown(content)}</div>
}
