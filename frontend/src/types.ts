export interface User { id: number; username: string; name: string; role: 'executive' | 'head' }

export interface PublicProject { id: number; name: string; rera_number: string; address: string }

export interface ChatMsg { role: 'buyer' | 'assistant'; content: string; at?: string }
export interface BookingInfo {
  id: number; starts_at: string; label: string; executive: string | null;
  project: string; address: string; map_url: string;
}
export interface SlotChip { id: number; starts_at: string; label: string; executive?: string | null }
export interface HandoffInfo { executive_name: string | null; reason: string }
export interface ChatState {
  project: PublicProject; language: string; messages: ChatMsg[];
  booking: BookingInfo | null; handoff: HandoffInfo | null;
}
export interface ChatReply {
  reply: string; slots: SlotChip[]; booking: BookingInfo | null; handoff: HandoffInfo | null;
}

export interface VisitSummary { booking_id: number; status: string; starts_at: string }
export interface Lead {
  id: number; name: string; phone: string; source: string; source_label: string;
  project: number; project_name: string; wants: string; language: string;
  consent_at: string | null; opted_out: boolean;
  assigned_to: number | null; assigned_to_name: string | null;
  duplicate_of: number | null; is_duplicate: boolean;
  created_at: string; first_response_at: string | null; latest_visit: VisitSummary | null;
}
export interface LeadDetailData extends Lead {
  bookings: { id: number; status: string; starts_at: string }[];
}
export interface LeadChat {
  messages: { role: 'buyer' | 'assistant'; content: string; cited?: number[]; at: string }[];
  needs: Record<string, unknown>;
  flagged: boolean; flag_reason: string;
  handoffs: { executive_name: string | null; reason: string; summary: string; at: string }[];
}
export interface FlaggedChat {
  id: number; lead_id: number; lead_name: string; project: string; reason: string;
  reviewed: boolean; summary: string; last_message: string; updated_at: string;
}

export interface SourceStats {
  source?: string; label?: string; leads: number;
  median_response_min: number | null; not_reached_48h_pct: number | null;
  booked: number; visited: number; no_show: number;
  show_up_rate_pct: number | null; lead_to_visit_pct: number | null;
  spend_inr: number; cost_per_visit_inr: number | null;
}
export interface DashboardData { days: number; overall: SourceStats; by_source: SourceStats[] }

export interface SlotRow { id: number; starts_at: string; executive: string; booked: boolean }
export interface Fact {
  id: number; project: number; title: string; text: string; is_registered: boolean; updated_at: string;
}
export interface Executive { id: number; name: string }

export const SOURCES: { value: string; label: string }[] = [
  { value: 'portal', label: 'Property portal' },
  { value: 'social', label: 'Social media ad' },
  { value: 'website', label: 'Website' },
  { value: 'hoarding', label: 'Hoarding call' },
];