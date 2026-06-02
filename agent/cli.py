from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config, write_default_config
from .io_utils import iter_jsonl, write_jsonl
from .model import Paper
from .tools.abstract_tools import summarize_abstract, translate_abstract_vi
from .tools.citation import apa_from_doi, bibtex_from_doi
from .tools.library import (
    DEFAULT_DB_PATH,
    add_paper,
    delete_paper,
    get_profile,
    list_papers,
    set_profile,
    update_note,
    update_tags,
)
from .tools.major_venues import MAJOR_VENUES, major_search
from .tools.paper_detail import fetch_detail
from .tools.paper_search import search_multi_source
from .tools.pdf_parser import parse_pdf
from .tools.recommend import recommend_from_openalex
from .tools.relevance import score_relevance
from .tools.web_fetch import fetch_paper_from_url


def _cmd_init(_: argparse.Namespace) -> int:
    created = write_default_config(DEFAULT_CONFIG_PATH)
    print(f"Created {DEFAULT_CONFIG_PATH}" if created else f"Config already exists: {DEFAULT_CONFIG_PATH}")
    return 0


def _print_papers(papers: list[Paper]) -> None:
    for p in papers:
        print(f"- {p.title} ({p.year or 'n/a'}) [{p.source}]")
        if p.venue:
            print(f"  venue: {p.venue}")
        if p.url:
            print(f"  url: {p.url}")
        if p.abstract:
            s = p.abstract.replace("\n", " ").strip()
            print(f"  abstract: {s[:400]}{'...' if len(s) > 400 else ''}")
        else:
            print("  abstract: (missing)")


def _cmd_fetch(args: argparse.Namespace) -> int:
    paper = fetch_paper_from_url(args.url)
    if args.out:
        write_jsonl(Path(args.out), [paper.to_dict()])
        print(f"Wrote 1 paper to {args.out}")
        return 0
    _print_papers([paper])
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    sources = [s.strip() for s in (args.sources.split(",") if args.sources else ["openalex"])]
    results = search_multi_source(
        query=args.query,
        sources=sources,
        limit=args.limit,
        openalex_email=cfg.openalex_email,
        venue=args.venue,
        year=args.year,
    )
    papers = [p.to_dict() for r in results for p in r.papers]
    if args.out:
        n = write_jsonl(Path(args.out), papers)
        print(f"Wrote {n} papers to {args.out}")
        return 0
    _print_papers([Paper(**p) for p in papers])  # type: ignore[arg-type]
    return 0


def _cmd_major_search(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    papers = major_search(
        venue_key=args.venue,
        query=args.query,
        year=args.year,
        limit=args.limit,
        openalex_email=cfg.openalex_email,
    )
    if args.out:
        n = write_jsonl(Path(args.out), [p.to_dict() for p in papers])
        print(f"Wrote {n} papers to {args.out}")
        return 0
    _print_papers(papers)
    return 0


def _cmd_detail(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    d = fetch_detail(identifier=args.id, id_type=args.type, openalex_email=cfg.openalex_email)
    if args.out:
        write_jsonl(Path(args.out), [d])
        print(f"Wrote detail to {args.out}")
        return 0
    print(json.dumps(d, ensure_ascii=False, indent=2))
    return 0


def _cmd_translate(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    inp = Path(args.input)
    out = Path(args.out)
    rows = []
    translated = 0
    for item in iter_jsonl(inp):
        abstract = (item.get("abstract") or "").strip()
        if abstract:
            provider = args.provider or cfg.llm_provider
            model = args.model or (cfg.openai_model if provider == "openai" else cfg.gemini_model)
            base_url = args.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
            item["abstract_vi"] = translate_abstract_vi(text=abstract, provider=provider, model=model, base_url=base_url)
            translated += 1
        rows.append(item)
    write_jsonl(out, rows)
    print(f"Wrote {out} (translated={translated})")
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    inp = Path(args.input)
    out = Path(args.out)
    rows = []
    summarized = 0
    for item in iter_jsonl(inp):
        abstract = (item.get("abstract") or "").strip()
        if abstract:
            provider = args.provider or cfg.llm_provider
            model = args.model or (cfg.openai_model if provider == "openai" else cfg.gemini_model)
            base_url = args.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
            item["abstract_summary"] = summarize_abstract(text=abstract, provider=provider, model=model, base_url=base_url)
            summarized += 1
        rows.append(item)
    write_jsonl(out, rows)
    print(f"Wrote {out} (summarized={summarized})")
    return 0


def _cmd_bibtex(args: argparse.Namespace) -> int:
    print(bibtex_from_doi(args.doi))
    return 0


def _cmd_cite(args: argparse.Namespace) -> int:
    print(apa_from_doi(args.doi))
    return 0


def _cmd_pdf_parse(args: argparse.Namespace) -> int:
    res = parse_pdf(Path(args.path), max_pages=args.max_pages)
    if args.out:
        write_jsonl(Path(args.out), [res.to_dict()])
        print(f"Wrote parse result to {args.out}")
        return 0
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    provider = args.provider or cfg.llm_provider
    base_url = args.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
    score = score_relevance(query=args.query, text=args.text, provider=provider, model=args.model, base_url=base_url)
    print(score)
    return 0


def _cmd_recommend(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    rec = recommend_from_openalex(seed_work_id=args.work_id, limit=args.limit, openalex_email=cfg.openalex_email)
    rows = []
    for k, ps in rec.items():
        for p in ps:
            d = p.to_dict()
            d["recommendation_type"] = k
            rows.append(d)
    if args.out:
        write_jsonl(Path(args.out), rows)
        print(f"Wrote {len(rows)} recommendations to {args.out}")
        return 0
    for k, ps in rec.items():
        print(f"== {k} ==")
        _print_papers(ps)
    return 0


def _cmd_lib_add(args: argparse.Namespace) -> int:
    if not args.url and not args.input:
        raise SystemExit("library add requires --url or --in")
    paper = fetch_paper_from_url(args.url).to_dict() if args.url else next(iter_jsonl(Path(args.input)))
    row_id = add_paper(Path(args.db), paper, tags=(args.tags.split(",") if args.tags else None), note=args.note)
    print(f"Added row_id={row_id}")
    return 0


def _cmd_lib_list(args: argparse.Namespace) -> int:
    rows = list_papers(Path(args.db), tag=args.tag, q=args.q, limit=args.limit)
    for r in rows:
        print(f"- [{r['row_id']}] {r['title']} ({r['year'] or 'n/a'}) tags={r['tags'] or ''}")
        if r.get("url"):
            print(f"  url: {r['url']}")
        if r.get("note"):
            print(f"  note: {r['note']}")
    return 0


def _cmd_lib_del(args: argparse.Namespace) -> int:
    delete_paper(Path(args.db), row_id=args.row_id)
    print("Deleted")
    return 0


def _cmd_lib_tag(args: argparse.Namespace) -> int:
    update_tags(Path(args.db), row_id=args.row_id, tags=args.tags.split(",") if args.tags else [])
    print("Updated tags")
    return 0


def _cmd_lib_note(args: argparse.Namespace) -> int:
    update_note(Path(args.db), row_id=args.row_id, note=args.note)
    print("Updated note")
    return 0


def _cmd_profile_set(args: argparse.Namespace) -> int:
    set_profile(Path(args.db), key=args.key, value=args.value)
    print("Saved")
    return 0


def _cmd_profile_show(args: argparse.Namespace) -> int:
    p = get_profile(Path(args.db))
    print(json.dumps(p, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="paper-agent")
    p.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_init = sub.add_parser("init", help="Create default config.toml")
    s_init.set_defaults(func=_cmd_init)

    s_fetch = sub.add_parser("fetch", help="Fetch a paper page by URL (best effort)")
    s_fetch.add_argument("--url", required=True)
    s_fetch.add_argument("--out")
    s_fetch.set_defaults(func=_cmd_fetch)

    s_search = sub.add_parser("search", help="Multi-source paper search")
    s_search.add_argument("--query", required=True)
    s_search.add_argument("--sources", default="openalex,semanticscholar,crossref,arxiv,dblp")
    s_search.add_argument("--venue")
    s_search.add_argument("--year", type=int)
    s_search.add_argument("--limit", type=int, default=25)
    s_search.add_argument("--out")
    s_search.set_defaults(func=_cmd_search)

    s_major = sub.add_parser("major-search", help="Search major venues (OpenReview first, fallback OpenAlex)")
    s_major.add_argument("--venue", required=True, help=f"One of: {', '.join(sorted(MAJOR_VENUES.keys()))}")
    s_major.add_argument("--year", type=int)
    s_major.add_argument("--query", required=True)
    s_major.add_argument("--limit", type=int, default=200)
    s_major.add_argument("--out")
    s_major.set_defaults(func=_cmd_major_search)

    s_detail = sub.add_parser("detail", help="Fetch paper detail by id/doi")
    s_detail.add_argument("--type", required=True, help="doi|openalex|semanticscholar|arxiv")
    s_detail.add_argument("--id", required=True)
    s_detail.add_argument("--out")
    s_detail.set_defaults(func=_cmd_detail)

    s_tr = sub.add_parser("translate", help="Translate abstracts to Vietnamese (OpenAI)")
    s_tr.add_argument("--in", dest="input", required=True)
    s_tr.add_argument("--out", required=True)
    s_tr.add_argument("--provider", choices=["openai", "gemini"])
    s_tr.add_argument("--model")
    s_tr.add_argument("--base-url")
    s_tr.set_defaults(func=_cmd_translate)

    s_sum = sub.add_parser("summarize", help="Summarize abstracts (OpenAI)")
    s_sum.add_argument("--in", dest="input", required=True)
    s_sum.add_argument("--out", required=True)
    s_sum.add_argument("--provider", choices=["openai", "gemini"])
    s_sum.add_argument("--model")
    s_sum.add_argument("--base-url")
    s_sum.set_defaults(func=_cmd_summarize)

    s_bib = sub.add_parser("bibtex", help="BibTeX from DOI")
    s_bib.add_argument("--doi", required=True)
    s_bib.set_defaults(func=_cmd_bibtex)

    s_cite = sub.add_parser("cite-apa", help="APA-ish citation from DOI")
    s_cite.add_argument("--doi", required=True)
    s_cite.set_defaults(func=_cmd_cite)

    s_pdf = sub.add_parser("pdf-parse", help="Parse PDF (abstract/method/experiments)")
    s_pdf.add_argument("--path", required=True)
    s_pdf.add_argument("--max-pages", type=int, default=8)
    s_pdf.add_argument("--out")
    s_pdf.set_defaults(func=_cmd_pdf_parse)

    s_score = sub.add_parser("score", help="Relevance score (embeddings cosine)")
    s_score.add_argument("--query", required=True)
    s_score.add_argument("--text", required=True)
    s_score.add_argument("--model", default="text-embedding-3-small")
    s_score.add_argument("--provider", choices=["openai", "gemini"])
    s_score.add_argument("--base-url")
    s_score.set_defaults(func=_cmd_score)

    s_rec = sub.add_parser("recommend", help="Recommend papers from a seed (OpenAlex)")
    s_rec.add_argument("--work-id", required=True)
    s_rec.add_argument("--limit", type=int, default=25)
    s_rec.add_argument("--out")
    s_rec.set_defaults(func=_cmd_recommend)

    s_lib = sub.add_parser("library", help="Saved papers library (sqlite)")
    s_lib.add_argument("--db", default=str(DEFAULT_DB_PATH))
    lib_sub = s_lib.add_subparsers(dest="lib_cmd", required=True)

    l_add = lib_sub.add_parser("add")
    l_add.add_argument("--url")
    l_add.add_argument("--in", dest="input")
    l_add.add_argument("--tags")
    l_add.add_argument("--note")
    l_add.set_defaults(func=_cmd_lib_add)

    l_list = lib_sub.add_parser("list")
    l_list.add_argument("--tag")
    l_list.add_argument("--q")
    l_list.add_argument("--limit", type=int, default=50)
    l_list.set_defaults(func=_cmd_lib_list)

    l_del = lib_sub.add_parser("delete")
    l_del.add_argument("--row-id", type=int, required=True)
    l_del.set_defaults(func=_cmd_lib_del)

    l_tag = lib_sub.add_parser("tag")
    l_tag.add_argument("--row-id", type=int, required=True)
    l_tag.add_argument("--tags", required=True)
    l_tag.set_defaults(func=_cmd_lib_tag)

    l_note = lib_sub.add_parser("note")
    l_note.add_argument("--row-id", type=int, required=True)
    l_note.add_argument("--note", required=True)
    l_note.set_defaults(func=_cmd_lib_note)

    s_prof = sub.add_parser("profile", help="User preference memory (sqlite)")
    s_prof.add_argument("--db", default=str(DEFAULT_DB_PATH))
    prof_sub = s_prof.add_subparsers(dest="profile_cmd", required=True)

    p_set = prof_sub.add_parser("set")
    p_set.add_argument("--key", required=True)
    p_set.add_argument("--value", required=True)
    p_set.set_defaults(func=_cmd_profile_set)

    p_show = prof_sub.add_parser("show")
    p_show.set_defaults(func=_cmd_profile_show)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
