/** Compatibility alias for callers migrating to the audience-aware DB welcome service. */
import { useWelcomeToast } from '@/composables/useWelcomeToast'

export function useAdminWelcome() {
  const welcome = useWelcomeToast()
  return { triggerAdminWelcome: welcome.triggerWelcome }
}
