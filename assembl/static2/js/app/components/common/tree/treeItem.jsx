/* eslint react/no-multi-comp: "off" */
// @flow
import * as React from 'react';
import { Map } from 'immutable';
import classnames from 'classnames';
import debounce from 'lodash/debounce';
import { CellMeasurerCache, List } from 'react-virtualized';

import { scrollToPost } from '../../../utils/hashLinkScroll';
import NuggetsManager from '../nuggetsManager';
import { PHASES } from '../../../constants';

type BaseProps = {
  id: string,
  identifier: string,
  phaseId: string,
  level: number,
  fullLevel?: string,
  rowIndex: number,
  hidden: boolean,
  originalLocale?: string,
  lang: string,
  contentLocaleMapping: Map<string, string>,
  listRef: List,
  nuggetsManager: NuggetsManager,
  cache: CellMeasurerCache,
  SeparatorComponent: React.Node,
  InnerComponentFolded: ({ nbPosts: number }) => React.Node,
  InnerComponent: (
    BaseProps & {
      contentLocale: string,
      numChildren: number,
      measureTreeHeight: (delay?: number) => void
    }
  ) => React.Node,
  fictionCommentCallbacks?: Object
};

type Props = {
  children: Array<TreeItem>
} & BaseProps;

type State = {
  expanded: boolean,
  visible: boolean
};

class Child extends React.PureComponent<Props, State> {
  static defaultProps = {
    InnerComponentFolded: () => null,
    level: 0,
    hidden: false
  };

  state = {
    expanded: true,
    visible: false
  };

  componentDidMount() {
    this.onScroll();
    window.addEventListener('scroll', this.onScroll);
    window.addEventListener('resize', this.onScroll);
  }

  componentWillUnmount() {
    this.stopListening();
  }

  holder: HTMLDivElement | null = null;

  scrollAnchor: { current: null | HTMLDivElement } = React.createRef();

  onScroll = debounce(() => {
    const holder = this.holder;
    if (!holder) {
      return;
    }
    const box = holder.getBoundingClientRect();
    const pageYOffset = window.pageYOffset;
    const top = box.top + pageYOffset;
    // visible if the top of the box is in viewport or next page
    const isVisible = top < pageYOffset + 2 * window.innerHeight && top > pageYOffset;
    if (isVisible) {
      this.setState(() => ({
        visible: true
      }));
      this.stopListening();
    }
  }, 100);

  stopListening() {
    window.removeEventListener('scroll', this.onScroll);
    window.removeEventListener('resize', this.onScroll);
  }

  resizeTreeHeight = (delay: number = 0) => {
    // This function will be called by each post rendered, so we delay the
    // recomputation until no post are rendered in 200ms to avoid unnecessary lag.
    const { listRef, cache, rowIndex, nuggetsManager } = this.props;
    cache.clear(rowIndex, 0);
    if (listRef) {
      let minRowIndex: number | null = listRef.minRowIndex; // minRowIndex from which to recompute row heights
      let timeoutId: TimeoutID | null = listRef.timeoutId;
      if (!minRowIndex) {
        listRef.minRowIndex = null;
      }
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      minRowIndex = Math.min(minRowIndex || rowIndex, rowIndex);
      timeoutId = setTimeout(() => {
        // if listRef.Grid is null, it means it has been unmounted, so we are now on a new List
        if (listRef.Grid) {
          // In Firefox (tested on version 59), recomputing row heights can jump back the page scroll
          // to the same post (The scrollTop from the Grid component is fine.),
          // potentially a post with a youtube video, but may be a coincidence.
          // Saving pageYOffset and restoring it after recomputeRowHeights fixes the issue.
          const pageYOffset = window.pageYOffset;
          listRef.recomputeRowHeights(minRowIndex);
          window.scrollTo({ top: pageYOffset, left: 0 });
          nuggetsManager.update();
          // recompute height only for rows (top post) starting at rowIndex
        }
        minRowIndex = null;
        timeoutId = null;
      }, delay);
    }
  };

  expandCollapse = (event: SyntheticEvent<HTMLDivElement>) => {
    event.stopPropagation();
    this.setState(
      state => ({ expanded: !state.expanded }),
      () => {
        this.resizeTreeHeight(0);
      }
    );
  };

  expandCollapseHandler = (event: SyntheticEvent<HTMLDivElement>, expanded: boolean) => {
    if (expanded) {
      this.scrollToElement();
    }
    this.expandCollapse(event);
  };

  renderToggleLink = (expanded: boolean, indented: boolean) => (
    <div
      ref={this.scrollAnchor}
      onClick={(event) => {
        this.expandCollapseHandler(event, expanded);
      }}
      className={indented ? 'expand-indented' : 'expand'}
    >
      {expanded ? <span className="assembl-icon-minus-circled" /> : <span className="assembl-icon-plus-circled" />}
    </div>
  );

  scrollToElement = () => {
    scrollToPost(this.scrollAnchor);
  };

  render() {
    const {
      id,
      children,
      identifier,
      phaseId,
      lang,
      originalLocale,
      fullLevel,
      level,
      hidden,
      rowIndex, // the index of the row (i.e. level 0 item) in the List
      contentLocaleMapping,
      InnerComponent,
      InnerComponentFolded,
      SeparatorComponent,
      nuggetsManager,
      listRef,
      cache,
      fictionCommentCallbacks
    } = this.props;
    const { expanded, visible } = this.state;
    const numChildren = children ? children.length : 0;
    const contentLocale = contentLocaleMapping.getIn([id, 'contentLocale'], originalLocale);
    // Define forwarded props according to identifier value
    let forwardProps = {
      ...this.props,
      contentLocale: contentLocale,
      numChildren: numChildren
    };

    // Push additional props from Tree.jsx to InnerComponent when identifier is brightMirror
    // We want to use some Tree.jsx functions to handle collapse/expand behavior for the list of fiction comments
    if (identifier === PHASES.brightMirror) {
      forwardProps = {
        ...forwardProps,
        fictionCommentCallbacks: {
          ...forwardProps.fictionCommentCallbacks,
          expanded: expanded,
          expandCollapseCallbackFromTree: event => this.expandCollapseHandler(event, expanded)
        }
      };
    }

    delete forwardProps.children;
    // InnerComponent, the post, is only rendered when the Child appears in the viewport or next page
    const { hash } = window.location;
    let isVisible = visible;
    // load right away the shared post
    let hashid;
    if (hash !== '') {
      hashid = hash.replace('#', '').split('?')[0];
      isVisible = hashid === id || isVisible;
    }

    return (
      <div
        className={classnames(`level level-${level}`, {
          'border-left child-level': level > 0,
          'no-shift': level > 3,
          'padding-right': level > 4,
          hidden: hidden
        })}
        id={id}
        ref={(el) => {
          this.holder = el;
          if (el && hashid === id) {
            scrollToPost(el, false);
          }
        }}
      >
        {isVisible ? (
          <InnerComponent {...forwardProps} measureTreeHeight={this.resizeTreeHeight} />
        ) : (
          <div style={{ height: 0.5 * window.innerHeight }} />
        )}
        {numChildren > 0 ? (
          <React.Fragment>
            {identifier !== PHASES.brightMirror ? this.renderToggleLink(expanded, level < 4) : null}
            {children.map((child, idx) => {
              const fullLevelArray: Array<string> = fullLevel ? fullLevel.split('-') : [];
              fullLevelArray[level] = `${idx}`;
              return (
                <Child
                  key={child.id}
                  {...child}
                  identifier={identifier}
                  phaseId={phaseId}
                  hidden={!expanded}
                  contentLocaleMapping={contentLocaleMapping}
                  lang={lang}
                  level={level + 1}
                  fullLevel={fullLevelArray.join('-')}
                  rowIndex={rowIndex}
                  InnerComponent={InnerComponent}
                  InnerComponentFolded={InnerComponentFolded}
                  SeparatorComponent={SeparatorComponent}
                  nuggetsManager={nuggetsManager}
                  listRef={listRef}
                  cache={cache}
                  fictionCommentCallbacks={fictionCommentCallbacks}
                />
              );
            })}
          </React.Fragment>
        ) : null}
        {numChildren > 0 && !expanded ? (
          <div
            className="postfolded-container"
            onClick={(event) => {
              this.expandCollapseHandler(event, expanded);
            }}
          >
            <div className="post-folded">
              <InnerComponentFolded nbPosts={numChildren} />
            </div>
          </div>
        ) : null}
      </div>
    );
  }
}

export default Child;