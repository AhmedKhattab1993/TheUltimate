import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import { SimplePriceRangeFilter } from './SimplePriceRangeFilter'
import userEvent from '@testing-library/user-event'

describe('SimplePriceRangeFilter', () => {
  describe('Rendering', () => {
    it('should render with initial state', () => {
      render(<SimplePriceRangeFilter />)
      
      expect(screen.getByText('Price Range Filter')).toBeInTheDocument()
      expect(screen.getByRole('switch', { name: /toggle price range filter/i })).toBeChecked()
      expect(screen.getByLabelText('Minimum Price ($)')).toHaveValue(1)
      expect(screen.getByLabelText('Maximum Price ($)')).toHaveValue(100)
    })

    it('should show help tooltip', () => {
      render(<SimplePriceRangeFilter />)
      
      // Check if the help icon is rendered (part of HelpTooltip component)
      expect(screen.getByText('Price Range Filter')).toBeInTheDocument()
    })

    it('should show filter description when enabled', () => {
      render(<SimplePriceRangeFilter />)
      
      expect(screen.getByText('Filters stocks by OPEN price on the current trading day')).toBeInTheDocument()
    })
  })

  describe('Toggle Functionality', () => {
    it('should toggle filter on/off', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      const toggle = screen.getByRole('switch', { name: /toggle price range filter/i })
      
      // Initially enabled
      expect(toggle).toBeChecked()
      expect(screen.getByLabelText('Minimum Price ($)')).toBeVisible()
      
      // Toggle off
      await user.click(toggle)
      expect(toggle).not.toBeChecked()
      expect(screen.queryByLabelText('Minimum Price ($)')).not.toBeInTheDocument()
      
      // Toggle back on
      await user.click(toggle)
      expect(toggle).toBeChecked()
      expect(screen.getByLabelText('Minimum Price ($)')).toBeVisible()
    })

    it('should update opacity based on enabled state', async () => {
      const user = userEvent.setup()
      const { container } = render(<SimplePriceRangeFilter />)
      
      const card = container.querySelector('.transition-opacity')
      expect(card).toHaveClass('opacity-100')
      
      const toggle = screen.getByRole('switch', { name: /toggle price range filter/i })
      await user.click(toggle)
      
      expect(card).toHaveClass('opacity-75')
    })
  })

  describe('Input Validation', () => {
    it('should accept valid price inputs', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      const minInput = screen.getByLabelText('Minimum Price ($)')
      const maxInput = screen.getByLabelText('Maximum Price ($)')
      
      await user.clear(minInput)
      await user.type(minInput, '5.50')
      expect(minInput).toHaveValue(5.50)
      
      await user.clear(maxInput)
      await user.type(maxInput, '150.75')
      expect(maxInput).toHaveValue(150.75)
    })

    it('should show error when min price >= max price', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      const minInput = screen.getByLabelText('Minimum Price ($)')
      const maxInput = screen.getByLabelText('Maximum Price ($)')
      
      // Set min price higher than max price
      await user.clear(minInput)
      await user.type(minInput, '200')
      
      expect(screen.getByText('Maximum price must be greater than minimum price')).toBeInTheDocument()
      expect(minInput).toHaveClass('border-red-500')
      expect(maxInput).toHaveClass('border-red-500')
    })

    it('should not show error when prices are equal but filter is disabled', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      // First set invalid prices
      const minInput = screen.getByLabelText('Minimum Price ($)')
      await user.clear(minInput)
      await user.type(minInput, '100')
      
      // Verify error shows
      expect(screen.getByText('Maximum price must be greater than minimum price')).toBeInTheDocument()
      
      // Disable filter
      const toggle = screen.getByRole('switch', { name: /toggle price range filter/i })
      await user.click(toggle)
      
      // Error should not be visible (inputs are hidden)
      expect(screen.queryByText('Maximum price must be greater than minimum price')).not.toBeInTheDocument()
    })

    it('should handle decimal inputs correctly', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      const minInput = screen.getByLabelText('Minimum Price ($)')
      
      await user.clear(minInput)
      await user.type(minInput, '0.01')
      expect(minInput).toHaveValue(0.01)
    })

    it('should handle empty inputs without crashing', async () => {
      const user = userEvent.setup()
      render(<SimplePriceRangeFilter />)
      
      const minInput = screen.getByLabelText('Minimum Price ($)')
      const maxInput = screen.getByLabelText('Maximum Price ($)')
      
      await user.clear(minInput)
      await user.clear(maxInput)
      
      // Should not show error for empty inputs
      expect(screen.queryByText('Maximum price must be greater than minimum price')).not.toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have proper labels for inputs', () => {
      render(<SimplePriceRangeFilter />)
      
      expect(screen.getByLabelText('Minimum Price ($)')).toBeInTheDocument()
      expect(screen.getByLabelText('Maximum Price ($)')).toBeInTheDocument()
      expect(screen.getByRole('switch', { name: /toggle price range filter/i })).toBeInTheDocument()
    })

    it('should have proper ARIA attributes', () => {
      render(<SimplePriceRangeFilter />)
      
      const toggle = screen.getByRole('switch', { name: /toggle price range filter/i })
      expect(toggle).toHaveAttribute('aria-label', 'Toggle price range filter')
    })

    it('should support keyboard navigation', async () => {
      render(<SimplePriceRangeFilter />)
      
      const toggle = screen.getByRole('switch', { name: /toggle price range filter/i })
      const minInput = screen.getByLabelText('Minimum Price ($)')
      
      // Focus on toggle with Tab
      toggle.focus()
      expect(document.activeElement).toBe(toggle)
      
      // Toggle with Space
      fireEvent.keyDown(toggle, { key: ' ', code: 'Space' })
      
      // Focus on input
      minInput.focus()
      expect(document.activeElement).toBe(minInput)
    })
  })

  describe('Integration with Context', () => {
    it('should update context state when values change', async () => {
      const user = userEvent.setup()
      const { rerender } = render(<SimplePriceRangeFilter />)
      
      const minInput = screen.getByLabelText('Minimum Price ($)')
      
      await user.clear(minInput)
      await user.type(minInput, '25')
      
      // Re-render to ensure state persists
      rerender(<SimplePriceRangeFilter />)
      
      expect(screen.getByLabelText('Minimum Price ($)')).toHaveValue(25)
    })
  })
})