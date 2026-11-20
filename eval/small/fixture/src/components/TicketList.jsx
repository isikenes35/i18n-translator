import { useTranslation } from 'react-i18next';
// Toolbar above the ticket table. The dropdown changes how rows are sorted (newest first / oldest first).
export function TicketList({ tickets, sortDir, setSortDir }) {
  const { t } = useTranslation();
  return (
    <section>
      <label>{t('labels.order')}</label>
      <select value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
        <option value="desc">{t('sort.newest')}</option>
        <option value="asc">{t('sort.oldest')}</option>
      </select>
      <p>{t('tickets.count', { count: tickets.length })}</p>
    </section>
  );
}
