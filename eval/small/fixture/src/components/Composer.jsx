import { useTranslation } from 'react-i18next';
// Text box at the top of a board where a member writes an update and publishes it to the board feed.
export function Composer({ onPublish, draft }) {
  const { t } = useTranslation();
  return (
    <div>
      <textarea placeholder={t('composer.placeholder')} value={draft} />
      <button onClick={onPublish}>{t('actions.post')}</button>
    </div>
  );
}
