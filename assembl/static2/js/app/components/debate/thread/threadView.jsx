// @flow
import React from 'react';
import { Grid } from 'react-bootstrap';
import Permissions, { connectedUserCan } from '../../../utils/permissions';
import TopPostFormContainer from '../../../components/debate/common/topPostFormContainer';
import { Tree } from '../../../components/common/tree';
import Post from '../common/post';
import FoldedPost from '../common/post/foldedPost';
import InfiniteSeparator from '../../../components/common/infiniteSeparator';
import { getIsPhaseCompletedById } from '../../../utils/timeline';
import type { ContentLocaleMapping } from '../../../actions/actionTypes';
import ThreadPostsFilterMenu from '../common/postsFilter/thread/menu';
import { defaultDisplayPolicy } from '../common/postsFilter/policies';

type Props = {
  isUserConnected: boolean,
  ideaId: string,
  contentLocaleMapping: ContentLocaleMapping,
  refetchIdea: Function,
  lang: string,
  noRowsRenderer: Function,
  posts: Array<Post>,
  initialRowIndex: ?number,
  identifier: string,
  phaseId: string,
  timeline: Timeline,
  messageViewOverride: string,
  postsDisplayPolicy?: PostsDisplayPolicy,
  routerParams: RouterParams
};

class ThreadView extends React.Component<Props> {
  // failed to type it React$Ref<HTMLDivElement>
  threadViewRef: any;

  static defaultProps = {
    postsDisplayPolicy: defaultDisplayPolicy
  };

  componentWillMount(): void {
    this.threadViewRef = React.createRef();
  }

  scrollToTop = () => {
    // scrollMargin is only about esthetic
    const scrollMargin = 160;
    window.scrollTo({
      top: this.threadViewRef.current.getBoundingClientRect().y + window.pageYOffset - scrollMargin
    });
  };

  render() {
    const {
      postsDisplayPolicy,
      isUserConnected,
      ideaId,
      contentLocaleMapping,
      refetchIdea,
      lang,
      noRowsRenderer,
      posts,
      initialRowIndex,
      identifier,
      phaseId,
      timeline,
      messageViewOverride,
      routerParams
    } = this.props;
    const isPhaseCompleted = getIsPhaseCompletedById(timeline, phaseId);
    return (
      <div>
        {(!isUserConnected || connectedUserCan(Permissions.ADD_POST)) && !isPhaseCompleted ? (
          <TopPostFormContainer
            ideaId={ideaId}
            refetchIdea={refetchIdea}
            topPostsCount={posts.length}
            routerParams={routerParams}
          />
        ) : null}
        <Grid fluid className="background-grey">
          <div ref={this.threadViewRef} id="thread-view" className="max-container background-grey">
            <ThreadPostsFilterMenu stickyOffset={60} stickyTopPosition={200} onFiltersUpdate={this.scrollToTop} />
            <div className="content-section">
              <Tree
                sharedProps={{ postsDisplayPolicy: postsDisplayPolicy }}
                contentLocaleMapping={contentLocaleMapping}
                lang={lang}
                data={posts}
                initialRowIndex={initialRowIndex}
                InnerComponent={Post}
                InnerComponentFolded={FoldedPost}
                noRowsRenderer={noRowsRenderer}
                SeparatorComponent={InfiniteSeparator}
                identifier={identifier}
                phaseId={phaseId}
                messageViewOverride={messageViewOverride}
              />
            </div>
          </div>
        </Grid>
      </div>
    );
  }
}

export default ThreadView;