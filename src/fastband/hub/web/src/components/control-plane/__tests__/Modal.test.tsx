/**
 * Tests for Modal Component.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '../../../test/utils'
import { Modal } from '../Modal'

describe('Modal', () => {
  it('does not render when isOpen is false', () => {
    render(
      <Modal isOpen={false} onClose={() => {}} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    expect(screen.queryByText('Test Modal')).not.toBeInTheDocument()
    expect(screen.queryByText('Modal content')).not.toBeInTheDocument()
  })

  it('renders when isOpen is true', () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    expect(screen.getByText('Test Modal')).toBeInTheDocument()
    expect(screen.getByText('Modal content')).toBeInTheDocument()
  })

  it('calls onClose when backdrop is clicked', () => {
    const handleClose = vi.fn()

    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    // Click the backdrop (first div with backdrop class)
    const backdrop = document.querySelector('.modal-backdrop-grid')
    if (backdrop) {
      fireEvent.click(backdrop)
    }

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn()

    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    // Find and click the close button
    const closeButton = screen.getByRole('button')
    fireEvent.click(closeButton)

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when Escape key is pressed', () => {
    const handleClose = vi.fn()

    render(
      <Modal isOpen={true} onClose={handleClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('renders footer when provided', () => {
    render(
      <Modal
        isOpen={true}
        onClose={() => {}}
        title="Test Modal"
        footer={<button>Save</button>}
      >
        <p>Modal content</p>
      </Modal>
    )

    expect(screen.getByText('Save')).toBeInTheDocument()
  })

  it('applies correct size class', () => {
    const { container, rerender } = render(
      <Modal isOpen={true} onClose={() => {}} title="Small Modal" size="sm">
        <p>Content</p>
      </Modal>
    )

    expect(container.querySelector('.max-w-md')).toBeInTheDocument()

    rerender(
      <Modal isOpen={true} onClose={() => {}} title="Large Modal" size="lg">
        <p>Content</p>
      </Modal>
    )

    expect(container.querySelector('.max-w-2xl')).toBeInTheDocument()
  })

  it('prevents body scroll when open', () => {
    const { unmount } = render(
      <Modal isOpen={true} onClose={() => {}} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    )

    expect(document.body.style.overflow).toBe('hidden')

    unmount()

    expect(document.body.style.overflow).toBe('unset')
  })
})
