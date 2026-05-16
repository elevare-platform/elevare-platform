import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormField, FormMessage } from '@/components/ui/form'
import { WorkLocationToggle } from '@/components/jobs/WorkLocationToggle'
import { cn } from '@/lib/utils'

// Zod schema — Requirements 5.4, 5.5, 5.6
const jobSchema = z
  .object({
    title: z.string().min(3, 'Title must be at least 3 characters'),
    description: z.string().min(10, 'Description must be at least 10 characters'),
    location: z.string().min(1, 'Location is required'),
    contract_type: z.enum(
      ['FULL_TIME', 'PART_TIME', 'CONTRACT', 'FREELANCE', 'INTERNSHIP'],
      { error: 'Select a contract type' }
    ),
    work_model: z
      .enum(['REMOTE', 'HYBRID', 'ONSITE'])
      .optional()
      .or(z.literal('')),
    work_location: z.enum(['LOCAL', 'INTERNATIONAL'], {
      error: 'Select a work location',
    }),
    salary_min: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be a positive number').optional()
    ),
    salary_max: z.preprocess(
      (v) => (v === '' || v == null ? undefined : Number(v)),
      z.number().positive('Must be a positive number').optional()
    ),
  })
  .refine(
    (data) => {
      if (data.salary_min != null && data.salary_max != null) {
        return data.salary_max >= data.salary_min
      }
      return true
    },
    {
      message: 'Salary max must be greater than or equal to salary min',
      path: ['salary_max'],
    }
  )

const selectClass = cn(
  'flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
  'disabled:cursor-not-allowed disabled:opacity-50'
)

/**
 * JobForm — shared create/edit form for job postings
 *
 * @param {Object} props
 * @param {Object} [props.defaultValues] - Pre-filled values for edit mode
 * @param {Function} props.onSubmit - Called with validated form data
 * @param {boolean} [props.loading] - Disables submit button while true
 * @param {string|null} [props.error] - Server-side error message to display
 */
export function JobForm({ defaultValues, onSubmit, loading = false, error = null }) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      title: '',
      description: '',
      location: '',
      contract_type: undefined,
      work_model: '',
      work_location: undefined,
      salary_min: '',
      salary_max: '',
      ...defaultValues,
    },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      {/* Title — Req 5.1, 5.4 */}
      <FormField>
        <Label htmlFor="title">Job title</Label>
        <Input
          id="title"
          placeholder="e.g. Senior Software Engineer"
          {...register('title')}
        />
        <FormMessage>{errors.title?.message}</FormMessage>
      </FormField>

      {/* Description — Req 5.1, 5.5 */}
      <FormField>
        <Label htmlFor="description">Description</Label>
        <textarea
          id="description"
          rows={6}
          placeholder="Describe the role, responsibilities, and requirements…"
          className={cn(
            'flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm',
            'placeholder:text-text-muted resize-y',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
          {...register('description')}
        />
        <FormMessage>{errors.description?.message}</FormMessage>
      </FormField>

      {/* Location — Req 5.1 */}
      <FormField>
        <Label htmlFor="location">Location</Label>
        <Input
          id="location"
          placeholder="e.g. Lagos, Nigeria"
          {...register('location')}
        />
        <FormMessage>{errors.location?.message}</FormMessage>
      </FormField>

      {/* Contract type + Work model — side by side on md+ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="contract_type">Contract type</Label>
          <select id="contract_type" className={selectClass} {...register('contract_type')}>
            <option value="">Select contract type</option>
            <option value="FULL_TIME">Full Time</option>
            <option value="PART_TIME">Part Time</option>
            <option value="CONTRACT">Contract</option>
            <option value="FREELANCE">Freelance</option>
            <option value="INTERNSHIP">Internship</option>
          </select>
          <FormMessage>{errors.contract_type?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="work_model">Work model (optional)</Label>
          <select id="work_model" className={selectClass} {...register('work_model')}>
            <option value="">Select work model</option>
            <option value="REMOTE">Remote</option>
            <option value="HYBRID">Hybrid</option>
            <option value="ONSITE">Onsite</option>
          </select>
          <FormMessage>{errors.work_model?.message}</FormMessage>
        </FormField>
      </div>

      {/* Work location toggle — Req 5.1 */}
      <FormField>
        <Label>Work location</Label>
        <Controller
          name="work_location"
          control={control}
          render={({ field }) => (
            <WorkLocationToggle
              value={field.value ?? null}
              onChange={field.onChange}
            />
          )}
        />
        <FormMessage>{errors.work_location?.message}</FormMessage>
      </FormField>

      {/* Salary range — optional, Req 5.1, 5.6 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField>
          <Label htmlFor="salary_min">Salary min (₦, optional)</Label>
          <Input
            id="salary_min"
            type="number"
            min={0}
            placeholder="e.g. 500000"
            {...register('salary_min')}
          />
          <FormMessage>{errors.salary_min?.message}</FormMessage>
        </FormField>

        <FormField>
          <Label htmlFor="salary_max">Salary max (₦, optional)</Label>
          <Input
            id="salary_max"
            type="number"
            min={0}
            placeholder="e.g. 900000"
            {...register('salary_max')}
          />
          <FormMessage>{errors.salary_max?.message}</FormMessage>
        </FormField>
      </div>

      {/* Server-side error — Req 5.7, 5.8 */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Submit — disabled while loading, Req 5.9 */}
      <Button type="submit" className="w-full" size="lg" disabled={loading}>
        {loading ? (
          <>
            <Loader2 size={16} className="mr-2 animate-spin" />
            Saving…
          </>
        ) : (
          'Save job'
        )}
      </Button>
    </form>
  )
}
