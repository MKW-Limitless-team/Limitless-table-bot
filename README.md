# Limitless Table Bot

Standalone Python Discord bot for MKW Limitless table workflows.

## Setup

1. Create a virtual environment and install dependencies from `requirements.txt`.
2. Edit `config.json`:
   - set `token`
   - confirm `base_url` (defaults to `http://wfc.blazico.nl`)
   - optionally change `state_dir` and `data_dir`
3. Run:

```bash
python app.py
```

## Notes

- This app is Limitless-only.
- Table state is stored locally under the configured state directory as pickle files.
- Environment variables still work as fallback, but `config.json` is now the main configuration path.
